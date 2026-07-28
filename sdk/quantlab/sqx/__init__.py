"""SQX CLI integration for QuantLab AI.

Provides the real CLI wrapper for dispatching CFX campaigns to a live
SQX daemon via its HTTP command API, along with the CampaignMonitor
background watcher and related data models.
"""

from quantlab.sqx.campaign_monitor import CampaignMonitor, WatcherEvent
from quantlab.sqx.cli_wrapper import dispatch_campaign
from quantlab.sqx.project_builder import create_project, remove_project

__all__ = [
    "dispatch_campaign",
    "create_project",
    "remove_project",
    "CampaignMonitor",
    "WatcherEvent",
]
