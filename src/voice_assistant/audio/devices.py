"""Audio device enumeration helpers."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def list_devices() -> list[dict]:
    """Return all audio devices with key metadata."""
    try:
        import sounddevice as sd

        devices = []
        for idx, dev in enumerate(sd.query_devices()):
            devices.append(
                {
                    "index": idx,
                    "name": dev["name"],
                    "max_input_channels": dev["max_input_channels"],
                    "max_output_channels": dev["max_output_channels"],
                    "default_samplerate": dev["default_samplerate"],
                    "hostapi": sd.query_hostapis(dev["hostapi"])["name"],
                }
            )
        return devices
    except Exception as exc:
        logger.error("Could not enumerate audio devices: %s", exc)
        return []


def pick_default_input(prefer_usb: bool = True) -> Optional[int]:
    """Return device index for the preferred input device."""
    try:
        import sounddevice as sd

        devices = list_devices()
        inputs = [d for d in devices if d["max_input_channels"] > 0]

        if prefer_usb:
            usb = [d for d in inputs if "usb" in d["name"].lower()]
            if usb:
                return usb[0]["index"]

        default = sd.query_devices(kind="input")
        return int(default["index"]) if default else None
    except Exception as exc:
        logger.error("Could not pick default input: %s", exc)
        return None


def pick_default_output(prefer_usb: bool = False) -> Optional[int]:
    """Return device index for the preferred output device."""
    try:
        import sounddevice as sd

        devices = list_devices()
        outputs = [d for d in devices if d["max_output_channels"] > 0]

        if prefer_usb:
            usb = [d for d in outputs if "usb" in d["name"].lower()]
            if usb:
                return usb[0]["index"]

        default = sd.query_devices(kind="output")
        return int(default["index"]) if default else None
    except Exception as exc:
        logger.error("Could not pick default output: %s", exc)
        return None
