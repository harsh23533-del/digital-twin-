"""
Web Bluetooth component — reads live heart rate using the VIEWER's own
browser Bluetooth adapter (Chrome/Edge only), not a server's. This is
what powers the "Live BLE (this browser — Web Bluetooth)" data source
in app.py — it works the same way whether the app is run locally or
deployed and opened on someone else's device, since the browser itself
does the connecting.

Needs no extra Python package (declare_component is part of Streamlit
core); the whole implementation is the vanilla-JS file next to this
module. It only works with devices that implement the standard
Bluetooth Heart Rate service (0x180D) — most budget smartwatches,
including the Noise ColorFit Pro 3 used during development, do not
expose it. See docs/live_watch.md.
"""

import os

import streamlit.components.v1 as components

_COMPONENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_bluetooth")
_component = components.declare_component("web_bluetooth_reading", path=_COMPONENT_DIR)


def web_bluetooth_reading(key: str = "web_bluetooth_reading") -> dict:
    """Render the "Pair a device" button and return the latest message the
    browser has sent. Always a dict; before anything happens it's
    {"status": "idle"}. Possible "status" values: idle, connected,
    disconnected, error. A "connected" message may or may not include
    "heart_rate" yet — the device is paired but the first notification
    hasn't arrived. "device_name" and "error" are present when relevant.
    """
    value = _component(key=key, default=None)
    return value if isinstance(value, dict) else {"status": "idle"}
