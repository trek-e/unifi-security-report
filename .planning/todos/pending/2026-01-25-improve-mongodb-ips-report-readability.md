---
created: 2026-01-25T17:46
title: Improve MongoDB IPS report readability
area: reports
files:
  - src/unifi_scanner/reports/templates/threat_section.html
  - src/unifi_scanner/analysis/ips/analyzer.py
---

## Problem

When IPS events are collected via MongoDB (SSH fallback), the report shows repetitive "Blocked Threat" entries with no distinguishing information:

```
BLOCKED Blocked Threat
Security event in category: blocked (14 blocked)
BLOCKED Blocked Threat
Security event in category: blocked (4 blocked)
...
```

MongoDB stores raw data (source IP, dest IP, timestamp, severity) but NOT signature names. The signature names visible in UniFi's UI come from encrypted rule databases not accessible via MongoDB.

Currently the report groups threats but displays generic labels, making it hard to:
- Identify which external IPs are attacking
- See which internal hosts are targeted
- Understand the scope of threats

## Solution

Display the actual IP addresses available from MongoDB instead of generic "Blocked Threat" labels:

1. Show source IP in threat title (e.g., "Blocked from 45.33.32.156")
2. Show destination/target IP (internal device being protected)
3. Group by source IP to show repeat offenders
4. Add note explaining signature names unavailable via MongoDB

Template changes to threat_section.html to conditionally render IP-based display when signature is missing/generic.
