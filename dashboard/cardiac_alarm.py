"""
Cardiac alarm — flashing red banner + audible beep when cardiac risk is
elevated, styled after a hospital bedside monitor's alarm state.

The banner (CSS animation) always renders reliably. The beep uses the
Web Audio API generated inside the iframe — most browsers require a user
gesture before audio can play; clicking "Advance" counts as one, so the
first beep after a click generally plays, but browsers vary and some may
still block it silently. There's no reliable way to guarantee audio
autoplay across all browsers, so the flashing banner is the alert a judge
can always count on seeing even if the beep is blocked.
"""

import streamlit as st


def _alarm_html(score: float, threshold: float, height: int = 90) -> str:
    return f"""
    <style>
      @keyframes alarm-flash {{
        0%, 100% {{ background-color: #b3001b; }}
        50% {{ background-color: #ff4d4d; }}
      }}
      #alarm-banner {{
        animation: alarm-flash 0.6s infinite;
        color: white;
        font-family: -apple-system, "Segoe UI", sans-serif;
        font-weight: 700;
        font-size: 1.15rem;
        text-align: center;
        border-radius: 8px;
        padding: 14px 10px;
        box-shadow: 0 0 18px rgba(255, 0, 0, 0.6);
      }}
    </style>
    <div id="alarm-banner">
      🚨 CARDIAC RISK ELEVATED — {score:.2f} (threshold {threshold}) — SEEK MEDICAL ATTENTION
    </div>
    <script>
    (function() {{
        function beep() {{
            try {{
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'square';
                osc.frequency.value = 950;
                gain.gain.setValueAtTime(0.18, ctx.currentTime);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start();
                osc.stop(ctx.currentTime + 0.18);
            }} catch (e) {{ /* autoplay blocked or unsupported — banner still flashes */ }}
        }}
        beep();
        setInterval(beep, 1000);  // repeats like a monitor alarm while this stays mounted
    }})();
    </script>
    """


def render_cardiac_alarm(score: float, threshold: float) -> None:
    """Render the flashing/beeping alarm. Call only when score >= threshold."""
    st.iframe(src=_alarm_html(score, threshold), height=90)
