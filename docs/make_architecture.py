"""
Regenerates docs/architecture.png (the architecture diagram used in the README).

Run from the repo root:
    python3 docs/make_architecture.py

Needs matplotlib, which is a docs-only dependency (not in requirements.txt):
    pip install matplotlib
"""

import os

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

matplotlib.use("Agg")

BG = "#F3F4F1"
DARK = "#10262B"
HEART = "#FF4462"
TEAL = "#1B7F79"
AMBER = "#C98A1B"
GREY = "#4A5A57"

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture.png")


def box(ax, x, y, w, h, title, sub, color):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.18",
        fc=color, ec="#0a1a1d", lw=1.4,
    ))
    ax.text(x + w / 2, y + h - 0.32, title, ha="center", va="center",
            color="white", fontsize=11.5, fontweight="bold")
    ax.text(x + w / 2, y + h / 2 - 0.22, sub, ha="center", va="center",
            color="white", fontsize=9.2, linespacing=1.5, alpha=0.92)


def arrow(ax, p1, p2, label=None, style="-|>", ls="-", label_offset=(0, 0)):
    ax.annotate("", xy=p2, xytext=p1, arrowprops=dict(
        arrowstyle=style, lw=1.7, color="#222", ls=ls, shrinkA=2, shrinkB=2,
    ))
    if label:
        mx = (p1[0] + p2[0]) / 2 + label_offset[0]
        my = (p1[1] + p2[1]) / 2 + label_offset[1]
        ax.text(mx, my, label, ha="center", va="center", fontsize=8.6, color="#222",
                bbox=dict(fc=BG, ec="none", pad=1.5))


def main():
    fig, ax = plt.subplots(figsize=(14, 8.4), dpi=150)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8.4)
    ax.axis("off")

    ax.text(7, 8.0, "Digi Twin — Cardiac Digital Twin Architecture", ha="center",
            fontsize=17, fontweight="bold", color=DARK)

    box(ax, 0.6, 6.0, 5.4, 1.35, "Cleveland Heart Disease CSV",
        "data/cardiac/cleveland_heart.csv\n(303 rows, 13 features)", GREY)
    box(ax, 8.0, 6.0, 5.4, 1.35, "DummySimulator",
        "one vitals reading per tick: heart rate, SpO2, resting BP\n"
        "occasional cardiac stress episodes", GREY)

    box(ax, 4.6, 3.95, 4.8, 1.55, "Twin Engine",
        "PatientState per patient  +  scheduler.tick()\n"
        "rolling vitals buffer, latest risk score", DARK)

    box(ax, 0.6, 1.95, 6.2, 1.5, "Cardiac Module",
        "rolling features (last 10 readings) -> XGBoost risk score\n"
        "+ SHAP top-3 contributing factors", TEAL)
    box(ax, 9.6, 1.95, 3.8, 1.5, "tests/test_engine.py",
        "parity  |  60-tick run\nthreshold alerts  |  multi-patient", AMBER)

    box(ax, 1.6, 0.2, 10.8, 1.35, "app.py — Streamlit dashboard",
        "patient selector  |  live vitals tiles  |  risk trend + SHAP  |  "
        "alert log + alarm banner  |  3D patient header", HEART)

    arrow(ax, (3.3, 6.0), (3.3, 3.45), "trains once,\ncached in artifacts/", ls="--")
    arrow(ax, (10.7, 6.0), (8.0, 5.5), "vitals reading")
    arrow(ax, (6.2, 3.95), (5.0, 3.45), "state in / risk out", style="<|-|>",
          label_offset=(1.1, 0.05))
    arrow(ax, (10.4, 3.45), (8.6, 3.95), "verifies")
    arrow(ax, (3.7, 1.95), (4.6, 1.55))
    arrow(ax, (8.0, 3.95), (8.6, 1.55), "state + risk scores", label_offset=(-1.25, 0.0))

    fig.savefig(OUT_PATH, facecolor=BG, bbox_inches="tight", pad_inches=0.25)
    print(f"saved {OUT_PATH}")


if __name__ == "__main__":
    main()
