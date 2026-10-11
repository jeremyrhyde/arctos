"""Load the shared YAML configs and open the CAN bus they describe."""

import glob
import pathlib

import can
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def load(name):
    """Load config/config_<name>.yaml."""
    with open(CONFIG_DIR / f"config_{name}.yaml") as f:
        return yaml.safe_load(f) or {}


def open_bus(channel=None):
    cfg = load("can")
    host = cfg.get("host", {})
    channel = channel or host.get("channel", "auto")
    if channel == "auto":
        ports = sorted(glob.glob("/dev/cu.usbmodem*"))
        if not ports:
            raise SystemExit("No USB-CAN adapter found (/dev/cu.usbmodem*). Is it plugged in?")
        channel = ports[0]
    return can.Bus(interface=host.get("interface", "slcan"), channel=channel, bitrate=cfg["bitrate"])
