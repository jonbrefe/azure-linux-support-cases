"""Configuration handling for triage_extract."""

import json
import os

DEFAULT_CONFIG = {
    "scrub_mode": "none",           # none | light | strict
    "include_all_logs": False,
    "enable_perf_parsing": False,
    "vm_size_limits_db_path": None,  # Path to custom VM limits JSON
    "disk_tiers_db_path": None,      # Path to custom disk tiers JSON
}


def load_config(path=None):
    """Load configuration from a JSON file, merged with defaults.

    Returns the default config if path is None or the file does not exist.
    """
    config = dict(DEFAULT_CONFIG)
    if path is None:
        return config

    path = os.path.abspath(path)
    if not os.path.isfile(path):
        return config

    with open(path, "r") as f:
        user_config = json.load(f)

    for key in DEFAULT_CONFIG:
        if key in user_config:
            config[key] = user_config[key]

    return config
