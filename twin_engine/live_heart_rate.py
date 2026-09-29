"""
Live BLE heart-rate source.

Reads real-time heart rate from any device that implements the standard
Bluetooth **Heart Rate Service** (0x180D) / **Heart Rate Measurement**
characteristic (0x2A37) — e.g. a Polar H10 chest strap, many Garmin/Wahoo
straps, and some smartwatches.

It does NOT work with devices that only expose a vendor-proprietary
service and no standard Heart Rate Service — this was true of the
original Noise ColorFit Pro 3 used during development (see
docs/live_watch.md). Point this at any device that DOES advertise 0x180D
and it works the same way.

Runs its own asyncio event loop in a background thread so it can be
driven from Streamlit's synchronous script-rerun model: call `start()`
once, then `get_latest()` on every tick to read the most recent reading
without blocking the UI thread.

Requires `bleak` (see requirements-live.txt) and a real Bluetooth
adapter on the machine running `streamlit run` — this will not work on
a cloud host with no Bluetooth hardware.
"""

import asyncio
import threading
import time
from typing import Optional

HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

STALE_AFTER_SEC = 10.0  # a reading older than this is treated as "no signal"


def parse_hr_measurement(data: bytes) -> int:
    """Decode the Heart Rate Measurement characteristic per the Bluetooth
    SIG spec: byte 0 is a flags bitfield whose bit 0 selects an 8-bit
    (byte 1) vs 16-bit (bytes 1-2, little-endian) heart-rate value."""
    flags = data[0]
    if flags & 0x01:
        return int.from_bytes(data[1:3], byteorder="little")
    return data[1]


class LiveHeartRateSource:
    """Background BLE client exposing the most recent heart-rate reading."""

    def __init__(self, name_filter: Optional[str] = None):
        self.name_filter = name_filter or None
        self._latest_hr: Optional[int] = None
        self._last_update: float = 0.0
        self._device_name: Optional[str] = None
        self._status = "idle"  # idle | scanning | connected | error | stopped
        self._error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def status(self) -> str:
        return self._status

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def device_name(self) -> Optional[str]:
        return self._device_name

    def get_raw(self) -> Optional[dict]:
        """Return whatever the device last actually sent, with no
        freshness cutoff — unlike get_latest(), which is for feeding the
        twin and drops stale packets. Used for a live "here's what the
        device is broadcasting right now" readout in the UI."""
        if self._latest_hr is None:
            return None
        return {"heart_rate": self._latest_hr, "age_sec": time.time() - self._last_update}

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        """Start scanning/connecting in a background thread. Idempotent —
        calling it while already running does nothing."""
        if self.is_running():
            return
        self._stop_event.clear()
        self._status = "scanning"
        self._error = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def get_latest(self) -> Optional[dict]:
        """Return the latest reading as a vitals dict (heart_rate only —
        this service has no BP/SpO2), or None if there isn't one yet or
        it's gone stale (device likely out of range / disconnected)."""
        if self._latest_hr is None:
            return None
        if time.time() - self._last_update > STALE_AFTER_SEC:
            return None
        return {"heart_rate": self._latest_hr}

    def _notification_handler(self, _sender, data: bytearray) -> None:
        try:
            self._latest_hr = parse_hr_measurement(bytes(data))
            self._last_update = time.time()
        except (IndexError, ValueError) as exc:
            # Malformed packet — keep the last good reading rather than crash.
            self._error = f"parse error: {exc}"

    def _run(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception as exc:  # thread has no other way to surface this
            self._status = "error"
            self._error = str(exc)

    async def _main(self) -> None:
        try:
            from bleak import BleakClient, BleakScanner  # optional dependency
        except ImportError:
            self._status = "error"
            self._error = "bleak is not installed — run: pip install -r requirements-live.txt"
            return

        def _matches(device, adv) -> bool:
            has_hr_service = HR_SERVICE_UUID in [u.lower() for u in (adv.service_uuids or [])]
            if not has_hr_service:
                return False
            if self.name_filter:
                return bool(device.name) and self.name_filter.lower() in device.name.lower()
            return True

        device = await BleakScanner.find_device_by_filter(_matches, timeout=15.0)
        if device is None:
            self._status = "error"
            self._error = (
                "No device advertising the standard Heart Rate service (0x180D) was found "
                "in 15s. Many budget smartwatches (incl. Noise) don't expose this service — "
                "see docs/live_watch.md."
            )
            return

        try:
            async with BleakClient(device) as client:
                self._device_name = device.name or device.address
                self._status = "connected"
                await client.start_notify(HR_MEASUREMENT_UUID, self._notification_handler)
                while not self._stop_event.is_set():
                    await asyncio.sleep(0.5)
                await client.stop_notify(HR_MEASUREMENT_UUID)
        except Exception as exc:
            self._status = "error"
            self._error = str(exc)
        finally:
            if self._status != "error":
                self._status = "stopped"
