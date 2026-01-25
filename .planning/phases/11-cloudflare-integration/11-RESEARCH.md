# Phase 11: Cloudflare Integration - Research

**Researched:** 2026-01-25
**Domain:** Cloudflare API integration (WAF events, DNS analytics, tunnel status)
**Confidence:** HIGH

## Summary

This phase implements the Cloudflare integration to enrich UniFi security reports with edge-level security data. The research focused on three Cloudflare APIs: (1) GraphQL Analytics API for WAF/firewall events via the `firewallEventsAdaptive` dataset, (2) GraphQL Gateway analytics for DNS blocked queries (Zero Trust), and (3) REST API for tunnel status via the `cfd_tunnel` endpoint.

The official `cloudflare` Python SDK (v4.3.1) provides typed access to all required APIs. For WAF events, the GraphQL endpoint (`https://api.cloudflare.com/client/v4/graphql`) returns firewall events with action, source IP, country, path, user agent, and rule details. DNS analytics are available through the `gatewayResolverQueriesAdaptiveGroups` GraphQL dataset for Zero Trust Gateway users. Tunnel status comes from the REST API at `/accounts/{account_id}/cfd_tunnel` with status values: healthy, degraded, down, inactive.

The integration follows Phase 10's infrastructure: implements the `Integration` Protocol, uses `CLOUDFLARE_API_TOKEN` for credentials-only detection (per CONTEXT.md), and registers with `IntegrationRegistry`. The circuit breaker and timeout handling are already provided by `IntegrationRunner`.

**Primary recommendation:** Use the official `cloudflare` Python SDK (v4.3.1) with httpx for GraphQL queries. Implement three collectors (WAF, DNS, Tunnels) behind the Integration Protocol. Detect API availability at runtime (Gateway requires Zero Trust subscription).

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| cloudflare | 4.3.1 | Official Cloudflare Python SDK | Typed responses, async support via httpx, maintained by Cloudflare |
| httpx | 0.27+ | HTTP client for GraphQL requests | Already in project, async support, required by SDK |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.11+ | Response model validation (already in project) | Parsing Cloudflare API responses |
| structlog | 25.5+ | Structured logging (already in project) | Integration status logging |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| cloudflare SDK | Direct httpx GraphQL | SDK provides type hints, pagination, but adds dependency |
| cloudflare SDK | python-cloudflare (old) | Old library is archived, cloudflare-python is the new official SDK |

**Installation:**
```bash
pip install cloudflare>=4.3
# Or add to pyproject.toml dependencies:
# "cloudflare>=4.3"
```

## Architecture Patterns

### Recommended Project Structure
```
src/unifi_scanner/
├── integrations/
│   ├── cloudflare/           # Cloudflare integration module
│   │   ├── __init__.py       # Public exports, register with registry
│   │   ├── integration.py    # CloudflareIntegration class (Protocol impl)
│   │   ├── client.py         # CloudflareClient - API wrapper
│   │   ├── models.py         # Pydantic models for CF data
│   │   ├── waf.py            # WAF event collection logic
│   │   ├── dns.py            # DNS analytics collection logic
│   │   └── tunnels.py        # Tunnel status collection logic
```

### Pattern 1: Integration Protocol Implementation
**What:** Implement the `Integration` Protocol from Phase 10 infrastructure
**When to use:** Creating the Cloudflare integration entry point
**Example:**
```python
# Source: Phase 10 RESEARCH.md + Existing codebase patterns
from typing import Optional
from unifi_scanner.integrations.base import Integration, IntegrationResult
from unifi_scanner.integrations.registry import IntegrationRegistry

class CloudflareIntegration:
    """Cloudflare integration for WAF, DNS, and tunnel data."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self._token = getattr(settings, 'cloudflare_api_token', None)
        # Account ID needed for tunnel API, zone for WAF
        self._account_id = getattr(settings, 'cloudflare_account_id', None)

    @property
    def name(self) -> str:
        return "cloudflare"

    def is_configured(self) -> bool:
        """Token is the only required credential per CONTEXT.md."""
        return bool(self._token)

    def validate_config(self) -> Optional[str]:
        """No partial config possible with token-only approach."""
        return None  # Token either exists or doesn't

    async def fetch(self) -> IntegrationResult:
        """Fetch WAF events, DNS analytics, and tunnel status."""
        # Implementation delegates to sub-collectors
        ...

# Register at module import time
IntegrationRegistry.register(CloudflareIntegration)
```

### Pattern 2: GraphQL Query for WAF Events
**What:** Query `firewallEventsAdaptive` dataset for blocked requests
**When to use:** Collecting WAF block events for the report
**Example:**
```python
# Source: https://developers.cloudflare.com/analytics/graphql-api/tutorials/querying-firewall-events/
import httpx
from datetime import datetime, timedelta

GRAPHQL_ENDPOINT = "https://api.cloudflare.com/client/v4/graphql"

async def fetch_waf_events(
    token: str,
    zone_id: str,
    lookback_hours: int = 24,
    limit: int = 100,
) -> list[dict]:
    """Fetch WAF block events from Cloudflare GraphQL API."""

    now = datetime.utcnow()
    start = now - timedelta(hours=lookback_hours)

    query = """
    query GetFirewallEvents($zoneTag: string!, $start: Time!, $end: Time!, $limit: Int!) {
        viewer {
            zones(filter: {zoneTag: $zoneTag}) {
                firewallEventsAdaptive(
                    filter: {
                        datetime_geq: $start
                        datetime_leq: $end
                        action: "block"
                    }
                    limit: $limit
                    orderBy: [datetime_DESC]
                ) {
                    action
                    clientAsn
                    clientCountryName
                    clientIP
                    clientRequestPath
                    clientRequestHTTPHost
                    datetime
                    source
                    ruleId
                    userAgent
                }
            }
        }
    }
    """

    variables = {
        "zoneTag": zone_id,
        "start": start.isoformat() + "Z",
        "end": now.isoformat() + "Z",
        "limit": limit,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            GRAPHQL_ENDPOINT,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables},
        )
        response.raise_for_status()
        data = response.json()
        return data["data"]["viewer"]["zones"][0]["firewallEventsAdaptive"]
```

### Pattern 3: Tunnel Status via REST API
**What:** List tunnels and their health status
**When to use:** Checking if any Cloudflare tunnels exist and their status
**Example:**
```python
# Source: https://developers.cloudflare.com/api/python/resources/zero_trust/subresources/tunnels/
from cloudflare import Cloudflare

async def fetch_tunnel_status(token: str, account_id: str) -> list[dict]:
    """Fetch Cloudflare tunnel status.

    Returns empty list if no tunnels exist (skip section per CONTEXT.md).
    """
    client = Cloudflare(api_token=token)

    # List active tunnels (exclude deleted)
    tunnels = client.zero_trust.tunnels.list(
        account_id=account_id,
        is_deleted=False,
    )

    return [
        {
            "name": tunnel.name,
            "id": tunnel.id,
            "status": tunnel.status,  # healthy, degraded, down, inactive
            "created_at": tunnel.created_at,
        }
        for tunnel in tunnels
    ]
```

### Pattern 4: Zone Discovery (Claude's Discretion: All Zones)
**What:** Fetch all zones for the account to aggregate WAF events
**When to use:** When no specific zone is configured
**Example:**
```python
# Source: Cloudflare Python SDK patterns
from cloudflare import Cloudflare

async def get_zones(token: str) -> list[dict]:
    """Get all zones accessible by the API token."""
    client = Cloudflare(api_token=token)

    zones = client.zones.list()
    return [{"id": zone.id, "name": zone.name} for zone in zones]
```

### Pattern 5: Graceful API Detection (DNS Gateway)
**What:** Detect if Zero Trust Gateway is available before querying DNS analytics
**When to use:** DNS analytics requires Gateway (Zero Trust subscription)
**Example:**
```python
# Source: https://developers.cloudflare.com/cloudflare-one/insights/analytics/gateway/
async def is_gateway_available(token: str, account_id: str) -> bool:
    """Check if Zero Trust Gateway is available for DNS analytics.

    Per CONTEXT.md: Detect available APIs and show what's accessible.
    """
    query = """
    query CheckGateway($accountTag: string!) {
        viewer {
            accounts(filter: {accountTag: $accountTag}) {
                gatewayResolverQueriesAdaptiveGroups(limit: 1) {
                    count
                }
            }
        }
    }
    """
    try:
        # If query succeeds, Gateway is available
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GRAPHQL_ENDPOINT,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"query": query, "variables": {"accountTag": account_id}},
            )
            data = response.json()
            # Check for errors indicating Gateway not available
            if data.get("errors"):
                return False
            return True
    except Exception:
        return False
```

### Anti-Patterns to Avoid
- **Using Global API Key:** Per CONTEXT.md, use scoped API tokens only
- **Hardcoding zone IDs:** Discover zones dynamically or make configurable
- **Assuming Gateway exists:** Detect Gateway availability before querying DNS
- **Showing empty tunnel section:** Per CONTEXT.md, skip if no tunnels exist
- **Single query for all data:** Separate WAF, DNS, tunnels for isolation

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GraphQL client | Custom HTTP wrapper | Official cloudflare SDK or httpx | Handles pagination, errors, types |
| API authentication | Manual header handling | cloudflare SDK | Consistent token handling |
| Tunnel listing | Direct REST calls | cloudflare SDK `zero_trust.tunnels.list()` | Typed responses, pagination |
| ISO 8601 timestamps | Manual string formatting | datetime.isoformat() | Timezone handling, edge cases |
| Circuit breaker | Custom implementation | Phase 10's IntegrationRunner | Already handles timeouts, retries |

**Key insight:** The cloudflare SDK handles pagination, error responses, and type hints. For GraphQL (WAF/DNS), direct httpx is simpler since the SDK doesn't have a GraphQL-specific client - just POST to the endpoint with your query.

## Common Pitfalls

### Pitfall 1: GraphQL Query Time Limits
**What goes wrong:** Query returns empty results or errors for large time ranges
**Why it happens:** Free plans limit to 24h, Business to 72h, Enterprise to 30 days
**How to avoid:** Default to 24h lookback, make configurable, handle empty gracefully
**Warning signs:** Empty `firewallEventsAdaptive` array despite known events

### Pitfall 2: Missing Zone ID for Zone-Scoped Queries
**What goes wrong:** WAF queries fail because zone ID is required
**Why it happens:** GraphQL `firewallEventsAdaptive` is zone-scoped, not account-scoped
**How to avoid:** Discover zones first, then query each zone (or use configured zone)
**Warning signs:** GraphQL errors about missing `zoneTag` filter

### Pitfall 3: Gateway Not Available (No Zero Trust)
**What goes wrong:** DNS analytics query fails for users without Zero Trust subscription
**Why it happens:** `gatewayResolverQueriesAdaptiveGroups` requires Gateway
**How to avoid:** Detect availability first, gracefully skip if not available
**Warning signs:** GraphQL errors about unknown field or access denied

### Pitfall 4: Tunnel API Requires Account ID
**What goes wrong:** Tunnel list returns 404 or empty
**Why it happens:** Tunnel API is account-scoped, needs `account_id` parameter
**How to avoid:** Require `CLOUDFLARE_ACCOUNT_ID` for tunnel functionality, or derive from zones
**Warning signs:** Empty tunnel list despite having active tunnels

### Pitfall 5: Rate Limiting on GraphQL
**What goes wrong:** API returns 429 Too Many Requests
**Why it happens:** Too many concurrent or frequent queries
**How to avoid:** Single query per report, leverage existing circuit breaker
**Warning signs:** Intermittent failures with rate limit errors

### Pitfall 6: Token Scope Insufficient
**What goes wrong:** API returns 403 Forbidden for specific endpoints
**Why it happens:** API token doesn't have required permissions
**How to avoid:** Document required permissions: Zone Analytics:Read, Account Analytics:Read, Cloudflare Tunnel:Read
**Warning signs:** Some APIs work, others fail with permission errors

## Code Examples

Verified patterns from official sources:

### GraphQL WAF Events Query (Complete)
```python
# Source: https://developers.cloudflare.com/analytics/graphql-api/tutorials/querying-firewall-events/
import httpx
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

@dataclass
class WAFEvent:
    """A single WAF block event from Cloudflare."""
    timestamp: datetime
    action: str
    source_ip: str
    country: str
    path: str
    host: str
    rule_source: str  # waf, firewallrules, etc.
    rule_id: Optional[str]
    user_agent: str

GRAPHQL_ENDPOINT = "https://api.cloudflare.com/client/v4/graphql"

FIREWALL_EVENTS_QUERY = """
query GetFirewallEvents($zoneTag: string!, $start: Time!, $end: Time!, $limit: Int!) {
    viewer {
        zones(filter: {zoneTag: $zoneTag}) {
            firewallEventsAdaptive(
                filter: {
                    datetime_geq: $start
                    datetime_leq: $end
                    action: "block"
                }
                limit: $limit
                orderBy: [datetime_DESC]
            ) {
                action
                clientAsn
                clientCountryName
                clientIP
                clientRequestPath
                clientRequestHTTPHost
                datetime
                source
                ruleId
                userAgent
            }
        }
    }
}
"""

async def fetch_waf_events(
    token: str,
    zone_id: str,
    lookback_hours: int = 24,
    limit: int = 100,
) -> List[WAFEvent]:
    """Fetch WAF block events from Cloudflare."""

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=lookback_hours)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GRAPHQL_ENDPOINT,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "query": FIREWALL_EVENTS_QUERY,
                "variables": {
                    "zoneTag": zone_id,
                    "start": start.isoformat(),
                    "end": now.isoformat(),
                    "limit": limit,
                },
            },
        )
        response.raise_for_status()
        data = response.json()

        if data.get("errors"):
            raise ValueError(f"GraphQL errors: {data['errors']}")

        events = data["data"]["viewer"]["zones"][0]["firewallEventsAdaptive"]

        return [
            WAFEvent(
                timestamp=datetime.fromisoformat(e["datetime"].rstrip("Z")),
                action=e["action"],
                source_ip=e["clientIP"],
                country=e["clientCountryName"],
                path=e["clientRequestPath"],
                host=e["clientRequestHTTPHost"],
                rule_source=e["source"],
                rule_id=e.get("ruleId"),
                user_agent=e["userAgent"],
            )
            for e in events
        ]
```

### DNS Analytics Query (Gateway/Zero Trust)
```python
# Source: https://developers.cloudflare.com/cloudflare-one/insights/analytics/gateway/
from dataclasses import dataclass
from typing import List

@dataclass
class DNSAnalytics:
    """DNS analytics summary from Cloudflare Gateway."""
    total_queries: int
    blocked_queries: int
    allowed_queries: int
    top_blocked_domains: List[str]

DNS_ANALYTICS_QUERY = """
query GetDNSAnalytics($accountTag: string!, $start: Time!, $end: Time!) {
    viewer {
        accounts(filter: {accountTag: $accountTag}) {
            gatewayResolverQueriesAdaptiveGroups(
                filter: {
                    datetime_geq: $start
                    datetime_leq: $end
                }
                limit: 10000
            ) {
                count
                dimensions {
                    resolverDecision
                    queryName
                }
            }
        }
    }
}
"""

async def fetch_dns_analytics(
    token: str,
    account_id: str,
    lookback_hours: int = 24,
) -> Optional[DNSAnalytics]:
    """Fetch DNS analytics from Cloudflare Gateway.

    Returns None if Gateway is not available.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=lookback_hours)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            GRAPHQL_ENDPOINT,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "query": DNS_ANALYTICS_QUERY,
                "variables": {
                    "accountTag": account_id,
                    "start": start.isoformat(),
                    "end": now.isoformat(),
                },
            },
        )
        response.raise_for_status()
        data = response.json()

        if data.get("errors"):
            # Gateway not available or permission issue
            return None

        groups = data["data"]["viewer"]["accounts"][0]["gatewayResolverQueriesAdaptiveGroups"]

        total = 0
        blocked = 0
        blocked_domains = []

        for group in groups:
            count = group["count"]
            decision = group["dimensions"]["resolverDecision"]
            domain = group["dimensions"].get("queryName", "")

            total += count
            if decision in ("blocked", "blockedByCategory"):
                blocked += count
                if domain:
                    blocked_domains.append(domain)

        return DNSAnalytics(
            total_queries=total,
            blocked_queries=blocked,
            allowed_queries=total - blocked,
            top_blocked_domains=blocked_domains[:10],  # Top 10
        )
```

### Tunnel Status Collection
```python
# Source: https://developers.cloudflare.com/api/python/resources/zero_trust/subresources/tunnels/
from dataclasses import dataclass
from typing import List, Optional
from cloudflare import Cloudflare

@dataclass
class TunnelStatus:
    """Status of a Cloudflare Tunnel."""
    name: str
    tunnel_id: str
    status: str  # healthy, degraded, down, inactive

async def fetch_tunnel_status(
    token: str,
    account_id: str,
) -> List[TunnelStatus]:
    """Fetch tunnel status from Cloudflare.

    Returns empty list if no tunnels exist (per CONTEXT.md: skip section).
    """
    client = Cloudflare(api_token=token)

    try:
        tunnels = list(client.zero_trust.tunnels.list(
            account_id=account_id,
            is_deleted=False,
        ))
    except Exception:
        # Tunnel API not available or no permission
        return []

    return [
        TunnelStatus(
            name=t.name,
            tunnel_id=t.id,
            status=t.status,  # healthy, degraded, down, inactive
        )
        for t in tunnels
        if t.status != "inactive"  # Only show tunnels that have been run
    ]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| python-cloudflare (old SDK) | cloudflare-python (official) | 2024 | Old library archived, new SDK is official |
| Global API Key | Scoped API Tokens | Recommended since 2020 | Better security, per CONTEXT.md |
| REST API for analytics | GraphQL Analytics API | 2019 | Single endpoint, flexible queries |
| Argo Tunnel API | cfd_tunnel (Zero Trust) | 2022 | New endpoint, same functionality |

**Deprecated/outdated:**
- **python-cloudflare**: Archived repository, replaced by cloudflare-python
- **Global API Key**: Still works but not recommended, use API tokens
- **/tunnels endpoint**: Deprecated, use /cfd_tunnel instead

## Open Questions

Things that couldn't be fully resolved:

1. **Account ID Discovery**
   - What we know: Tunnel API needs account_id, can be derived from zones
   - What's unclear: Best UX - require config or auto-discover?
   - Recommendation: Auto-discover from first zone, allow override via `CLOUDFLARE_ACCOUNT_ID`

2. **Zone Selection Strategy**
   - What we know: WAF events are zone-scoped, can query multiple zones
   - What's unclear: Whether to aggregate all zones or show per-zone
   - Recommendation (Claude's Discretion): Query all accessible zones, aggregate events, note which zone each event came from

3. **WAF Event Grouping**
   - What we know: Events have rule_id, source, IP - all valid grouping options
   - What's unclear: Most useful grouping for security report
   - Recommendation (Claude's Discretion): Group by source (waf, firewallrules, etc.) then by rule, show top IPs

4. **DNS Analytics Without Gateway**
   - What we know: Standard Cloudflare DNS doesn't have analytics API
   - What's unclear: What to show for non-Gateway users
   - Recommendation: Skip DNS section entirely if Gateway not available (per CONTEXT.md graceful handling)

## Sources

### Primary (HIGH confidence)
- [Cloudflare Python SDK PyPI](https://pypi.org/project/cloudflare/) - Version 4.3.1, Python 3.8+
- [Cloudflare GraphQL Analytics docs](https://developers.cloudflare.com/analytics/graphql-api/) - firewallEventsAdaptive dataset
- [Cloudflare Firewall Events Tutorial](https://developers.cloudflare.com/analytics/graphql-api/tutorials/querying-firewall-events/) - Query examples
- [Cloudflare Zero Trust Tunnels API](https://developers.cloudflare.com/api/python/resources/zero_trust/subresources/tunnels/) - List tunnels method
- [Cloudflare Gateway Analytics](https://developers.cloudflare.com/cloudflare-one/insights/analytics/gateway/) - DNS datasets

### Secondary (MEDIUM confidence)
- [Cloudflare API Token Permissions](https://developers.cloudflare.com/fundamentals/api/reference/permissions/) - Permission scopes
- [Cloudflare python-cloudflare GraphQL example](https://github.com/cloudflare/python-cloudflare/blob/master/examples/example_graphql.py) - GraphQL pattern (old SDK but same API)

### Tertiary (LOW confidence)
- WebSearch results on Cloudflare tunnel status values - verified against API docs

## API Token Permissions Required

Per CONTEXT.md, use scoped API tokens. Required permissions:

| Permission | Scope | Purpose |
|------------|-------|---------|
| Zone > Analytics > Read | All zones (or specific) | WAF events via GraphQL |
| Account > Account Analytics > Read | Account | DNS Gateway analytics |
| Account > Cloudflare Tunnel > Read | Account | Tunnel status |
| Account > Zero Trust > Read | Account | Gateway detection |

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official cloudflare SDK documented, GraphQL API well-documented
- Architecture: HIGH - Follows Phase 10 patterns already in codebase
- Pitfalls: HIGH - Derived from official documentation and API constraints
- Code examples: HIGH - Based on official tutorials with minor adaptations

**Research date:** 2026-01-25
**Valid until:** 2026-02-25 (30 days - Cloudflare APIs are stable)
