# Connecting a real device — Live BLE (Web Bluetooth) mode

By default Digi Twin runs on `DummySimulator`. It can also read **live
heart rate** from a real Bluetooth device, as an alternative data source
you pick in the sidebar: **"Live BLE (this browser — Web Bluetooth)"**.

## How it works

It's a small custom Streamlit component (`dashboard/web_bluetooth/`)
built on the browser's
[`navigator.bluetooth`](https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API)
Web Bluetooth API — no extra Python package needed, since
`declare_component` is part of Streamlit core. It uses **your own
browser's** Bluetooth adapter, not a server's, so it works the same way
whether you're running this locally or someone else has it deployed and
opened it on their own device.

Clicking **"Pair a device"** opens the browser's own native device
picker — showing every nearby Bluetooth device, not just ones already
known to support heart rate — and you select your device there. Once
paired, it reads the standard Bluetooth **Heart Rate Service**
(`0x180D`) / **Heart Rate Measurement** characteristic (`0x2A37`).

## Requirements

- **Chrome or Edge only** — Web Bluetooth isn't implemented in Safari or
  Firefox.
- **HTTPS**, or `localhost` during local development.

## What works, and what doesn't

Any device that implements the standard Heart Rate service works —
chest straps (Polar H10, Wahoo TICKR, Garmin HRM) are the most
reliable, and some smartwatches expose it too.

**Most budget smartwatches do not.** During development, a Noise
ColorFit Pro 3 was tested via [nRF Connect](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-mobile):
its GATT services were Device Information, Generic Access, Generic
Attribute, and one vendor **Custom Service** (`0000af0-…`) with no
`0x180D` — the standard Heart Rate service was absent. The device will
still appear in the browser's pairing picker (it shows everything
nearby) and can be selected, but connecting to it then shows "doesn't
expose the standard Heart Rate service" — the limitation is the
device's firmware, not the Bluetooth stack asking.

### How to check what your device supports

1. Install [nRF Connect](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-mobile)
   on your phone.
2. Disconnect the watch from its own companion app first (BLE devices
   usually only accept one connection at a time).
3. Scan, connect to the watch, and open its **Client** tab.
4. Look for a service named **Heart Rate** / UUID `0x180D`. If it's not
   in the list, this mode won't be able to read live data from it.

## Using it

In the sidebar: pick **"Live BLE (this browser — Web Bluetooth)"**,
click **"Pair a device"**, and choose your device from the browser's
picker. The status line shows `idle`, `connected — <device name>`,
`disconnected`, or an error.

The Heart Rate service carries heart rate only — no blood pressure or
SpO2 — so this mode also shows a manual **Resting BP** number input,
which is merged into every reading so the model's rolling `trestbps`
feature still gets real input. SpO2 shows `—` in this mode.

## Known limitations

- **One device at a time**, shared across all patients — it doesn't
  track per-patient hardware.
- **Stale readings are dropped**, not shown: if no packet has arrived in
  the last 10 seconds (out of range, disconnected), that tick is simply
  skipped rather than showing an old number as if it were current.
- Prototype-grade error handling: there's no automatic reconnect after a
  real disconnect — click **"Pair a device"** again.
