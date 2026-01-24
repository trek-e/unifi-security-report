# Project Research Summary

**Project:** UniFi Log Analysis Service
**Domain:** Network log analysis and monitoring
**Researched:** 2026-01-24
**Confidence:** MEDIUM-HIGH

## Executive Summary

The UniFi Scanner service is a network log analysis tool that translates technical UniFi gateway logs into plain English reports for non-expert users. Research reveals this fills a genuine gap between enterprise SIEM tools (too complex) and consumer network monitors (too simple). The recommended approach uses a **Python-based ETL pipeline architecture** with scheduled batch processing, prioritizing stability and simplicity over real-time complexity.

The core technical challenge is integrating with UniFi's undocumented API, which varies significantly across device types (UDM Pro, UCG Ultra, legacy controllers) and changes without notice between firmware versions. The recommended stack uses Python 3.12+ with `unifi-controller-api` for API integration, Pydantic for data validation, APScheduler for job scheduling, and Jinja2 for report generation. The synchronous, polling-based architecture is appropriate for the v1 use case and avoids unnecessary async complexity.

Critical risks include authentication failures with cloud accounts (requires local accounts only), API breaking changes after firmware updates, and inconsistent log formats across device types. Mitigation strategies involve device-type detection, defensive parsing with graceful fallbacks, and abstraction layers that can adapt to API changes. The main product risk is alert fatigue from over-reporting, which research shows causes 67% of alerts to be ignored. Success depends on curating findings, strict severity classification, and genuinely plain English explanations with actionable remediation steps.

## Key Findings

### Recommended Stack

The stack prioritizes production-ready stability over cutting-edge technology. Python 3.12+ provides modern type hints and performance improvements while remaining stable through 2028. The container foundation uses `python:3.12-slim-bookworm` rather than Alpine to avoid musl libc compatibility issues with cryptography libraries.

**Core technologies:**
- **Python 3.12+**: Runtime with full type hint support and long EOL (2028)
- **unifi-controller-api 0.3.2**: Most actively maintained UniFi API client with typed models
- **Pydantic 2.x**: Rust-powered validation for log event models and configuration
- **APScheduler 3.11.2**: Cron-style scheduling without external dependencies
- **Jinja2 3.1.6**: Industry-standard templating for reports
- **structlog 25.5.0**: Structured logging with JSON output for production
- **paramiko 4.0.0**: SSH fallback for direct log access when API insufficient

**Key decisions:**
- Synchronous over async (polling architecture doesn't need async complexity)
- stdlib regex + Pydantic over log parsing libraries (UniFi logs require custom parsing)
- APScheduler over Celery (no distributed task complexity needed)
- Docker-first design (target users run containerized services)

**Confidence: MEDIUM-HIGH** — Core libraries verified via PyPI with recent release dates; UniFi API library has small community (11 stars) but active development.

### Expected Features

Research across network monitoring tools and competitive analysis reveals clear feature expectations. The core value proposition is translating technical logs into plain English with actionable remediation, which existing tools notably lack.

**Must have (table stakes):**
- Log collection from UniFi (API-first, SSH fallback)
- Severity categorization (map to low/medium/severe)
- Scheduled report generation (daily/weekly configurable)
- Email delivery via SMTP
- File output for archival
- Human-readable explanations (core differentiator)
- Issue deduplication (group repeats, show counts)
- Timestamps and device context

**Should have (competitive differentiators):**
- Plain English explanations for non-experts
- Actionable remediation steps for severe issues
- Risk context ("this is serious because...")
- Threat category explanations (map MITRE ATT&CK to plain language)
- Device-specific insights (which AP/switch had issues)
- Prioritized action items (rank by severity and fixability)

**Defer (v2+):**
- Real-time alerting (adds complexity, alert fatigue risk)
- Dashboard/GUI (scope creep, reports faster to ship)
- Issue trend tracking (requires historical storage)
- Network health score (nice-to-have aggregation)
- Multi-gateway support (architectural change)
- Custom rule creation (non-experts won't use)

**Anti-features (explicitly avoid):**
- Automatic remediation (risk of breaking network)
- Exhaustive alerting (causes alert fatigue)
- Raw log display (defeats purpose)
- Complex configuration (target users are non-experts)

**Confidence: MEDIUM** — Based on competitive analysis of UniFi Alarm Manager, Splunk, Graylog, Fing, Firewalla. Alert fatigue research is well-documented across multiple sources.

### Architecture Approach

The service follows a classic **five-stage ETL pipeline**: Collection → Parsing → Analysis → Report Generation → Delivery. This architecture separates concerns, enables independent testing of stages, and follows established patterns for log analysis systems. The batch processing model (not streaming) is appropriate for periodic reporting.

**Major components:**
1. **Log Collector** — Fetches raw logs via UniFi API (primary) or SSH (fallback), handles device-type-specific endpoints
2. **Log Parser** — Normalizes diverse formats (syslog, JSON, custom) into structured LogEntry objects using defensive parsing
3. **Analyzer (Rules Engine)** — Applies pattern-matching rules to detect issues, assigns severity (low/medium/severe), generates findings
4. **Finding Store** — In-memory accumulation and deduplication of findings for single-run processing
5. **Report Generator** — Jinja2 templates to create human-readable HTML/text reports from findings
6. **Delivery** — SMTP email and filesystem output with configurable channels
7. **Config Manager** — Pydantic-based validation of environment variables and YAML config

**Data flow:**
```
UniFi Gateway → Raw Logs → Normalized LogEntry → Finding (with severity/explanation) → Report → Email/File
```

**Key patterns:**
- **Pipeline Processor**: Each stage is pure function (input → output, no side effects)
- **Dependency Injection**: Components receive dependencies through constructor for testability
- **Configuration-Driven Rules**: Analysis rules defined in YAML for extensibility

**Confidence: HIGH** — ETL pipeline and rules engine patterns are well-established. UniFi-specific integration patterns verified through community libraries.

### Critical Pitfalls

Based on research across official Ubiquiti documentation and community integrations, five critical pitfalls emerged that could cause complete feature failure or require rewrites.

1. **Cloud/SSO Account Authentication Fails** — UniFi enforces MFA on all UI.com cloud accounts, breaking programmatic access. **Prevention:** Require local admin accounts only, detect MFA errors, provide specific setup guidance. **Phase: 1 (API Connection)**

2. **Device-Specific API Endpoint Variations** — UniFi has three different endpoint patterns (self-hosted on :8443, UniFi OS on :443 with `/proxy/network` prefix, UniFi OS Server on :11443). **Prevention:** Device type detection on first connection, abstracted URL builder. **Phase: 1 (API Connection)**

3. **Inconsistent Log Formats Across Devices** — Formats vary by device type and firmware version; CEF format only available through SIEM integration, not direct syslog. **Prevention:** Explicit format handlers per log type, defensive parsing with graceful fallbacks. **Phase: 2 (Log Parsing)**

4. **Session Expiration and Cookie Management** — Sessions expire based on idle timeout (as short as 1 minute), controller restarts, or firmware updates. **Prevention:** Auto re-auth on 401/403, store credentials for re-auth, health checks verify actual data retrieval. **Phase: 1 (API Connection)**

5. **API Breaking Changes After Firmware Updates** — Ubiquiti's undocumented API changes without notice; community wiki explicitly notes it's a "reverse engineering project." **Prevention:** Version detection, API response validation, abstraction layer for adaptability, monitor Ubiquiti releases. **Phase: 1 (API Connection), ongoing**

**Additional moderate pitfalls:**
- Alert fatigue from over-reporting (67% of alerts ignored industry-wide)
- IDS false positives without tuning guidance
- Jargon-heavy reports for non-technical users
- Docker container networking (mDNS `.local` addresses don't resolve)

**Confidence: HIGH** — Pitfalls verified through official Ubiquiti documentation, community libraries (Home Assistant UniFi integration, Art-of-WiFi API client), and SIEM integration guides.

## Implications for Roadmap

Based on component dependencies, feature priorities, and pitfall timing, research suggests a 5-6 phase structure:

### Phase 1: Foundation & API Connection
**Rationale:** Must establish reliable UniFi integration before any other work. API authentication and device detection are foundational; failures here block all downstream work.

**Delivers:**
- Config Manager with Pydantic validation (environment variables + YAML)
- Core data models (LogEntry, Finding, Report)
- UniFi API client with device type detection
- Session management and auto re-authentication
- Local vs cloud account detection

**Addresses features:**
- Log collection from UniFi (table stakes)
- Docker deployment foundation

**Avoids pitfalls:**
- Critical Pitfall #1: Cloud account authentication (local account requirement)
- Critical Pitfall #2: Device endpoint variations (detection logic)
- Critical Pitfall #4: Session expiration (auto re-auth)
- Critical Pitfall #5: Breaking changes (abstraction layer)

**Research flag:** SKIP — API integration patterns well-documented through unifi-controller-api library and community sources.

### Phase 2: Log Collection & Parsing
**Rationale:** Once API works, need to actually fetch and normalize logs. Parsing must handle multiple formats defensively from day one.

**Delivers:**
- Log collection via API (`get_events()`, `get_alarms()`)
- Multi-format parser (syslog, JSON detection)
- Defensive parsing with graceful fallbacks
- SSH fallback for direct log access
- Timestamp normalization (UTC handling)

**Addresses features:**
- Log parsing and normalization (table stakes)
- Timestamps and device context (table stakes)

**Avoids pitfalls:**
- Critical Pitfall #3: Inconsistent log formats (explicit format handlers)
- Minor Pitfall #12: Log location varies by device (path discovery)
- Minor Pitfall #13: Timezone confusion (UTC normalization)

**Research flag:** MAYBE — Log format variations may need deeper investigation. Start with CEF format from SIEM integration docs, but expect to iterate based on actual device outputs.

### Phase 3: Analysis Engine & Rules
**Rationale:** With normalized logs, build the intelligence layer that detects issues and assigns severity. This is the core value-add logic.

**Delivers:**
- Rules engine (pattern matching, severity assignment)
- Initial rule set (20-30 common issues covering security, connectivity, performance)
- Finding Store with deduplication
- Plain English explanation templates
- Remediation templates for severe issues

**Addresses features:**
- Severity categorization (table stakes)
- Human-readable explanations (core differentiator)
- Remediation steps for severe issues (differentiator)
- Issue deduplication (table stakes)

**Avoids pitfalls:**
- Moderate Pitfall #7: IDS false positives (context and tuning guidance)

**Research flag:** YES — Rule development requires domain expertise. May need `/gsd:research-phase` for common UniFi log patterns, IDS signature mappings, and remediation strategies per issue type.

### Phase 4: Report Generation
**Rationale:** Findings mean nothing without clear communication. This phase focuses on making output genuinely useful to non-experts.

**Delivers:**
- Jinja2 template system
- HTML and plain text report formats
- Severity-based grouping (severe first, then medium, then low)
- Report structure (summary, severe issues with remediation, medium/low sections)
- Subject line generation

**Addresses features:**
- Report generation templates (table stakes)
- Plain English output (core differentiator)
- Risk context for non-experts (differentiator)
- Threat category explanations (differentiator)
- Prioritized action items (differentiator)

**Avoids pitfalls:**
- Moderate Pitfall #6: Alert fatigue (severity-based filtering)
- Moderate Pitfall #8: Jargon-heavy reports (plain English focus)
- Minor Pitfall #14: Incomplete remediation guidance (step-by-step fixes)

**Research flag:** SKIP — Report structure and templating are straightforward. Writing quality depends more on domain knowledge from Phase 3 than research.

### Phase 5: Delivery & Scheduling
**Rationale:** With reports generated, need to get them to users reliably. Scheduling triggers the whole pipeline.

**Delivers:**
- SMTP email delivery (HTML with plaintext fallback)
- File output (configurable directory and format)
- APScheduler integration (cron-style triggers)
- Delivery retry logic
- Production Docker container

**Addresses features:**
- Email delivery (table stakes)
- File output (table stakes)
- Scheduled reports (table stakes)
- Docker deployment (table stakes)

**Avoids pitfalls:**
- Moderate Pitfall #10: Rate limiting (polling intervals, backoff)

**Research flag:** SKIP — SMTP and scheduling are well-documented patterns.

### Phase 6 (Optional): Hardening & Polish
**Rationale:** After core MVP works end-to-end, address edge cases and operational concerns.

**Delivers:**
- Extended rule set (50+ patterns)
- Error handling and logging improvements
- Device-specific credential guidance
- Network configuration documentation
- Deployment guides for different UniFi hardware types

**Avoids pitfalls:**
- Moderate Pitfall #9: Docker networking (documentation)
- Minor Pitfall #11: SSH credential complexity (guidance)

**Research flag:** SKIP — Incremental improvements based on user feedback.

### Phase Ordering Rationale

1. **API connection must come first** — All subsequent work depends on reliably fetching logs. Device detection and authentication pitfalls must be solved at foundation.

2. **Parsing before analysis** — Can't analyze what isn't normalized. Defensive parsing prevents brittleness from format variations.

3. **Analysis before reporting** — Need findings to report. Rule development is the intelligence layer.

4. **Report generation before delivery** — Must have content before worrying about delivery channels.

5. **Scheduling last** — Simplifies development to run manually until full pipeline proven.

This order also aligns with testing strategy: each phase builds on previous, allowing incremental integration testing.

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 3 (Analysis Engine):** Rule development requires domain expertise. Need to research:
  - Most common UniFi log patterns and their meanings
  - IDS/IPS signature mappings to plain English
  - Remediation strategies for top security/connectivity issues
  - False positive patterns and context clues

**Phases with standard patterns (skip research):**
- **Phase 1:** API integration patterns well-documented via unifi-controller-api library
- **Phase 2:** Parser architecture follows standard ETL patterns (may need format iteration but not research)
- **Phase 4:** Jinja2 templating is straightforward
- **Phase 5:** SMTP and scheduling are solved problems

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Core libraries verified via PyPI; unifi-controller-api is actively maintained but small community (11 stars); underlying patterns are solid |
| Features | MEDIUM | Competitive analysis based on WebSearch across multiple tools; table stakes features consistent across sources; differentiators inferred from gap analysis |
| Architecture | HIGH | ETL pipeline and rules engine are well-established patterns; component boundaries follow standard practice; UniFi-specific integration patterns verified through community libraries |
| Pitfalls | HIGH | Critical pitfalls verified through official Ubiquiti docs, community libraries, and SIEM integration guides; moderate pitfalls supported by industry research on alert fatigue |

**Overall confidence:** MEDIUM-HIGH

The architecture and patterns are solid (HIGH confidence). The main uncertainties are:
1. UniFi API stability and version variations (mitigated through abstraction)
2. Coverage of explanation/remediation knowledge base (addressed in Phase 3 research)
3. Log format edge cases across device types (addressed through defensive parsing)

### Gaps to Address

**Gap 1: Log Pattern Coverage**
- **Issue:** How many distinct UniFi log patterns exist? 50? 500? Unknown without access to live systems across device types.
- **Handling:** Start with top 20-30 most critical patterns in Phase 3. Build graceful handling for unknown patterns (capture raw, flag for later analysis). Iterate based on user feedback and real-world log samples.

**Gap 2: Explanation Quality for Non-Experts**
- **Issue:** "Plain English" is subjective. Research shows what NOT to do (jargon, raw log fields) but not exact phrasing.
- **Handling:** Draft explanation templates in Phase 3, validate with actual non-technical users before launch. Iterate based on comprehension testing.

**Gap 3: UniFi Controller Version Matrix**
- **Issue:** Which controller/firmware versions will the service support? API variations unknown without testing matrix.
- **Handling:** Document tested versions. Pin minimum supported version (recommend 7.x+). Implement version detection and warn on unsupported versions. Plan for API response validation to catch breaking changes early.

**Gap 4: SSH Fallback Necessity**
- **Issue:** Unclear if API provides sufficient log access or if SSH fallback is always needed.
- **Handling:** Implement API path first. Add SSH fallback in Phase 2 only if API proves insufficient. Monitor user feedback on log completeness.

**Gap 5: Report Frequency Preferences**
- **Issue:** Is daily too often? Weekly too infrequent? No user data.
- **Handling:** Make frequency configurable (hourly/daily/weekly). Default to daily. Gather feedback post-launch. Consider "digest" vs "immediate" modes in v2.

## Sources

### Primary (HIGH confidence)
- [Ubiquiti Help Center - Official UniFi API](https://help.ui.com/hc/en-us/articles/30076656117655-Getting-Started-with-the-Official-UniFi-API)
- [Ubiquiti Help Center - UniFi System Logs & SIEM Integration](https://help.ui.com/hc/en-us/articles/33349041044119-UniFi-System-Logs-SIEM-Integration)
- [PyPI unifi-controller-api](https://pypi.org/project/unifi-controller-api/) — v0.3.2, Dec 27, 2025
- [PyPI paramiko](https://pypi.org/project/paramiko/) — v4.0.0, Aug 4, 2025
- [PyPI APScheduler](https://pypi.org/project/APScheduler/) — v3.11.2, Dec 22, 2025
- [PyPI Jinja2](https://pypi.org/project/Jinja2/) — v3.1.6, Mar 5, 2025
- [PyPI structlog](https://pypi.org/project/structlog/) — v25.5.0, Oct 27, 2025
- [Pydantic Documentation](https://docs.pydantic.dev/latest/)

### Secondary (MEDIUM confidence)
- [Ubiquiti Community Wiki - UniFi Controller API](https://ubntwiki.com/products/software/unifi-controller/api)
- [Art-of-WiFi/UniFi-API-client](https://github.com/Art-of-WiFi/UniFi-API-client)
- [Home Assistant UniFi Integration](https://www.home-assistant.io/integrations/unifi/)
- [Huntress Support - Ubiquiti UniFi Syslog Devices](https://support.huntress.io/hc/en-us/articles/43357255053459-Ubiquiti-UniFi-Syslog-Devices)
- [LogicMonitor UniFi Monitoring](https://www.logicmonitor.com/support/ubiquiti-unifi-network-monitoring)
- [LogicMonitor - Alert Fatigue Best Practices](https://www.logicmonitor.com/blog/network-monitoring-avoid-alert-fatigue)
- [Rules Engine Design Pattern](https://tenmilesquare.com/resources/software-development/basic-rules-engine-design-pattern/)
- [Docker Best Practices 2025](https://collabnix.com/10-essential-docker-best-practices-for-python-developers-in-2025/)

### Tertiary (LOW confidence - needs validation)
- WeasyPrint version (PyPI fetch failed, verify during implementation)
- Exact API endpoint paths across all UniFi OS versions (community docs may lag official changes)

---
*Research completed: 2026-01-24*
*Ready for roadmap: yes*
