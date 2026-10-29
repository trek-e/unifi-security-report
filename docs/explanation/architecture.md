# About the Architecture

The UniFi Security Report is designed as a modular, extensible pipeline for transforming raw network logs into actionable security intelligence.

## Core Components

The system is built around four primary functional modules:

### 1. Data Collection (The Adapters)
The `UnifiClient` acts as the primary interface to the UniFi Controller. It handles:
- **Authentication**: Managing sessions and CSRF tokens.
- **Site Discovery**: Automatically detecting available sites.
- **Log Retrieval**: Fetching events, alarms, and device statistics via REST API.
- **Fallback Mechanisms**: Using SSH to query MongoDB directly on UDM-class devices when the API is insufficient (e.g., for IPS/IDS events).

### 2. Analysis Engine (The Orchestrator)
The `AnalysisEngine` is a pure orchestration component. It does not contain domain-specific logic; instead, it manages the lifecycle of various "Rules."

The engine supports two types of rules:
- **Stateless Rules**: Perform analysis on a single log entry in isolation (e.g., categorizing a single event).
- **Stateful Rules**: Maintain internal state across multiple analysis cycles (e.g., detecting a client flapping between access points over a 10-minute window).

The engine ensures **batch independence** by calling a `reset()` method on all stateful rules at the start of every analysis run.

### 3. Rule System (The Intelligence)
Rules are the heart of the scanner. Each rule is a discrete unit of logic that implements a specific security or health check.
- **Modularity**: New rules can be added by implementing the `BaseRule` interface without modifying the engine.
- **Complexity Management**: Rules are categorized by severity (Low, Medium, Severe) and type (Security, Health, Wireless).

### 4. Delivery (The Reporters)
Once analysis is complete, the results are passed to the delivery module, which handles:
- **Formatting**: Converting findings into human-readable HTML or plain text.
- **Routing**: Sending reports via Email (SMTP) or saving them to local files.
- **Scheduling**: Managing the timing of report generation via cron-like presets.

## Data Flow

1. **Ingestion**: `UnifiClient` fetches raw JSON data from the controller.
2. **Normalization**: Raw data is parsed into standardized internal models.
3. **Analysis**: The `AnalysisEngine` iterates through the normalized data, passing each entry to the registered rules.
4. **Aggregation**: Findings are collected, deduplicated, and summarized.
5. **Reporting**: The summary is formatted and delivered to the configured destinations.
