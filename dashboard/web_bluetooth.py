"""
Web Bluetooth component — reads live heart rate using the VIEWER's own
browser Bluetooth adapter (Chrome/Edge only), not the server's.

This is the browser-side counterpart to twin_engine/live_heart_rate.py,
which connects using the Bluetooth adapter of the machine running
`streamlit run` instead. Use this one when the app is opened by someone
else (deployed, or opened from a different device) and *their* device's
heart-rate monitor should be the one that connects — not the server's.

Needs no extra Python package (declare_component is part of Streamlit
core); the whole implementation is the vanilla-JS file next to this
module. Like the server-side source, it only works with devices that
implement the standard Bluetooth Heart Rate service (0x180D) — most
budget smartwatches, including the Noise ColorFit Pro 3 used during
development, do not expose it. See docs/live_watch.md.
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
