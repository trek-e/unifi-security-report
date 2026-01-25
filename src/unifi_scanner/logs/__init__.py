"""Log parsing modules for UniFi Scanner."""

from .api_collector import APICollectionError, APILogCollector
from .collector import LogCollectionError, LogCollector
from .parser import LogParser
from .ssh_collector import SSHCollectionError, SSHLogCollector
from .ws_collector import WSCollectionError, WSLogCollector

__all__ = [
    # Main orchestrator
    "LogCollector",
    "LogCollectionError",
    # API collector
    "APILogCollector",
    "APICollectionError",
    # SSH collector
    "SSHLogCollector",
    "SSHCollectionError",
    # WebSocket collector
    "WSLogCollector",
    "WSCollectionError",
    # Parser
    "LogParser",
]
