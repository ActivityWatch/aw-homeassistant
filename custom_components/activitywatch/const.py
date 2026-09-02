"""Constants for the ActivityWatch integration."""

from __future__ import annotations

from datetime import timedelta
import logging

DOMAIN = "activitywatch"

LOGGER = logging.getLogger(__package__)

CONF_HOSTS = "hosts"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_PORT = 5600
DEFAULT_UPDATE_INTERVAL = 60

# How long after the last watcher heartbeat we still consider a host active.
# aw-watcher-afk heartbeats continuously while the machine is in use, so a
# gap larger than this means the machine is off, asleep, or unreachable.
STALE_AFTER = timedelta(minutes=5)

# Consider a host "recently active" (preselected in the config flow) if its
# buckets were updated within this window.
RECENT_HOST_WINDOW = timedelta(days=7)

AFK_BUCKET_TYPE = "afkstatus"
WINDOW_BUCKET_TYPE = "currentwindow"
