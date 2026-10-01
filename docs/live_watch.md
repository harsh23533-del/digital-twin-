# Connecting a real device — Live BLE heart-rate mode

By default Digi Twin runs on `DummySimulator`. It can also read **live
heart rate** from a real Bluetooth device, as an alternative data source
you pick in the sidebar.

## What works, and what doesn't

The live source (`twin_engine/live_heart_rate.py`) speaks the standard
Bluetooth **Heart Rate Service** (`0x180D`) / **Heart Rate Measurement**
characteristic (`0x2A37`). Any device that implements this works the same
way — chest straps (Polar H10, Wahoo TICKR, Garmin HRM) are the most
reliable, and some smartwatches expose it too.

**Most budget smartwatches do not.** During development, a Noise ColorFit
Pro 3 was tested via [nRF Connect](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-mobile):
its GATT services were Device Information, Generic Access, Generic
Attribute, and one vendor **Custom Service** (`0000af0-…`) with no
`0x180D` — the standard Heart Rate service was absent, so this route
can't read from it. If your device doesn't advertise `0x180D`, `Connect`
in the sidebar will time out with "No device advertising the standard
Heart Rate service (0x180D) was found."

### How to check what your device supports

1. Install [nRF Connect](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-mobile)
   on your phone.
2. Disconnect the watch from its own companion app first (BLE devices
   usually only accept one connection at a time).
3. Scan, connect to the watch, and open its **Client** tab.
4. Look for a service named **Heart Rate** / UUID `0x180D`. If it's not
   in the list, this mode won't work with that device.

## Setup

Live mode needs `bleak`, which isn't in the default install so cloud
deployments don't need a Bluetooth stack:

```bash
pip install -r requirements-live.txt
```

Run the app on a machine with a real Bluetooth adapter (this will not
work on a cloud host with no Bluetooth hardware):

```bash
streamlit run app.py
```

In the sidebar: pick **Live BLE heart-rate monitor**, optionally type
part of the device's name to narrow the scan, and click **Connect** —
or use **Scan for nearby BLE devices** to see everything advertising
nearby and click **Connect** next to a specific one. The status line
shows `scanning`, `connected — <device name>`, or an error.

The Heart Rate service carries heart rate only — no blood pressure or
SpO2 — so live mode also shows a manual **Resting BP** number input,
which is merged into every reading so the model's rolling `trestbps`
feature still gets real input. SpO2 shows `—` in live mode.

## Known limitations

- **No auth/pairing UI.** Bonding is handled by the OS, not this app.
- **One device at a time**, shared across all patients — it doesn't
  track per-patient hardware.
- **Stale readings are dropped**, not shown: if no packet has arrived in
  the last 10 seconds (out of range, disconnected), `get_latest()`
  returns `None` and that tick is simply skipped rather than showing an
  old number as if it were current.
- Prototype-grade error handling: a malformed BLE packet is logged and
  ignored rather than crashing the connection, but there's no automatic
  reconnect after a real disconnect — click **Connect** again.

## Alternative: Live BLE (this browser — Web Bluetooth)

The sidebar also offers **"Live BLE (this browser — Web Bluetooth)"**,
a second, independent way to get a live heart rate — this one connects
using the **viewer's own browser Bluetooth adapter** instead of the
server's.

**Why this exists.** The server-side option above only works when
`streamlit run app.py` is executing on a machine with a real Bluetooth
adapter — fine for a solo demo on your own laptop, but useless once the
app is deployed or opened by someone else: their device's heart-rate
monitor can't be reached by the server's Bluetooth. Web Bluetooth mode
fixes that — the browser itself talks to whatever device the person
viewing the page pairs, with no server-side Bluetooth hardware needed at
all.

**How it works.** It's a small custom Streamlit component
(`dashboard/web_bluetooth/`) using the browser's
[`navigator.bluetooth`](https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API)
API — no extra Python package needed, since `declare_component` is part
of Streamlit core. Clicking **"Pair a device"** opens the browser's own
device picker; the person selects their device there, not in this app.

**Requirements:**
- **Chrome or Edge only** — Web Bluetooth isn't implemented in Safari or
  Firefox.
- **HTTPS**, or `localhost` during local development.
- The device picker shows **every** nearby Bluetooth device (not just
  ones already advertising the Heart Rate service), so a watch can be
  selected to try even if it turns out not to share data — same as the
  "Scan for nearby BLE devices" list in the server-side option above.
  But the same **0x180D-only** limitation still applies for actually
  reading data: it reads the standard Heart Rate service and nothing
  else, so the same devices that don't work with the server-side mode
  (including the Noise ColorFit Pro 3) will connect but then show
  "doesn't expose the standard Heart Rate service" — the limitation is
  the device's firmware, not which Bluetooth stack is asking.

Both live modes feed the twin the same way and share the same manual
Resting BP input; switching between them in the sidebar doesn't lose
your place in the simulator or any patient's history.
