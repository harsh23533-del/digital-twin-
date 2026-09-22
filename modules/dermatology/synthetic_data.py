"""
Synthetic dermoscopy-image generator + ABCD-rule feature extractor.

No DermNet dataset was accessible in this build environment (network is
restricted to package registries — no Kaggle/DermNet access), so this
module generates synthetic lesion images from first principles instead:
each class gets a distribution over the four classic dermoscopy ABCD
parameters (Asymmetry, Border irregularity, Color variegation, Diameter),
and images are rendered from those parameters. Features are then
re-extracted from the *pixels* (not read back from the generation
parameters), so the downstream classifier genuinely has to learn the
pixel -> class relationship rather than being handed the answer.

Swap in real DermNet images later by replacing `generate_dataset()`'s
image source and keeping `extract_features()` as the shared interface.
"""

from __future__ import annotations

import numpy as np

IMG_SIZE = 96

# Per-class ABCD parameter ranges (min, max), roughly ordered by severity,
# plus a distinct lesion base color per class (real dermoscopy cue: eczema
# reads red/inflamed, psoriasis pale/silvery, nevi brown, BCC pearly-pink,
# melanoma dark brown-black).
# asymmetry / border_irregularity / color_variegation: 0 (regular) - 1 (highly irregular)
# diameter: fraction of image radius the lesion occupies
CLASS_PARAMS: dict[str, dict] = {
    "healthy":              {"asymmetry": (0.00, 0.05), "border": (0.00, 0.05), "color_var": (0.00, 0.05), "diameter": (0.03, 0.10), "color": (222, 178, 150)},
    "eczema":                {"asymmetry": (0.05, 0.20), "border": (0.15, 0.35), "color_var": (0.10, 0.20), "diameter": (0.20, 0.40), "color": (205, 85, 80)},
    "psoriasis":             {"asymmetry": (0.05, 0.20), "border": (0.10, 0.25), "color_var": (0.08, 0.18), "diameter": (0.25, 0.50), "color": (215, 175, 175)},
    "benign_nevus":          {"asymmetry": (0.02, 0.12), "border": (0.02, 0.12), "color_var": (0.05, 0.15), "diameter": (0.08, 0.18), "color": (95, 60, 42)},
    "basal_cell_carcinoma":  {"asymmetry": (0.20, 0.40), "border": (0.25, 0.45), "color_var": (0.20, 0.35), "diameter": (0.18, 0.35), "color": (205, 150, 140)},
    "melanoma":              {"asymmetry": (0.40, 0.80), "border": (0.40, 0.80), "color_var": (0.40, 0.80), "diameter": (0.30, 0.60), "color": (45, 28, 24)},
}

CLASSES = list(CLASS_PARAMS.keys())

_SKIN_TONE = np.array([222.0, 178.0, 150.0])   # base background skin color (RGB)


def _radius_function(theta: np.ndarray, base_radius: float, asymmetry: float,
                      border: float, rng: np.random.Generator) -> np.ndarray:
    """Boundary radius as a function of angle theta — asymmetric + irregular."""
    # Asymmetry: two different mean radii on either side of a random axis.
    axis = rng.uniform(0, 2 * np.pi)
    side = np.cos(theta - axis) >= 0
    r = np.where(side, base_radius * (1 + asymmetry), base_radius * (1 - asymmetry * 0.6))

    # Border irregularity: sum of a few random-phase sine harmonics.
    for k in range(1, 5):
        amp = border * base_radius * (0.15 / k)
        phase = rng.uniform(0, 2 * np.pi)
        r = r + amp * np.sin(k * theta + phase)

    return np.clip(r, base_radius * 0.3, base_radius * 1.8)


def generate_image(cls: str, rng: np.random.Generator) -> tuple[np.ndarray, dict]:
    """Render one synthetic dermoscopy image for the given class.

    Returns (image as HxWx3 uint8 array, the sampled ABCD params — for
    dataset bookkeeping only, never fed to the feature extractor).
    """
    p = CLASS_PARAMS[cls]
    asymmetry = rng.uniform(*p["asymmetry"])
    border = rng.uniform(*p["border"])
    color_var = rng.uniform(*p["color_var"])
    diameter = rng.uniform(*p["diameter"])
    lesion_base = np.array(p["color"], dtype=np.float64)

    size = IMG_SIZE
    yy, xx = np.mgrid[0:size, 0:size]
    cx, cy = size / 2, size / 2
    dx, dy = xx - cx, yy - cy
    r = np.sqrt(dx ** 2 + dy ** 2)
    theta = np.arctan2(dy, dx)

    base_radius = diameter * size / 2
    boundary = _radius_function(theta, base_radius, asymmetry, border, rng)
    lesion_mask = r < boundary

    # Background: skin tone + mild texture noise.
    img = _SKIN_TONE + rng.normal(0, 4, size=(size, size, 3))

    # Lesion: base lesion color + variegation (per-pixel color noise scaled by color_var),
    # plus a soft radial gradient so edges aren't perfectly flat.
    variegation_noise = rng.normal(0, 40 * color_var, size=(size, size, 3))
    radial_shade = 1.0 - 0.15 * np.clip(r / np.maximum(boundary, 1e-6), 0, 1)
    lesion_color = (lesion_base[None, None, :] * radial_shade[..., None]) + variegation_noise
    img = np.where(lesion_mask[..., None], lesion_color, img)

    img = np.clip(img, 0, 255).astype(np.uint8)
    return img, {"asymmetry": asymmetry, "border": border, "color_var": color_var, "diameter": diameter}


def extract_features(img: np.ndarray) -> np.ndarray:
    """Extract 9 ABCD-inspired features purely from pixels (no ground-truth params used).

    1-3: mean R/G/B of the lesion region
    4-6: std R/G/B of the lesion region (color variegation proxy)
    7:   lesion area fraction (diameter proxy)
    8:   asymmetry score (fraction of pixels that differ from the horizontally-mirrored mask)
    9:   border irregularity (mask perimeter / sqrt(area) — higher = more jagged boundary)
    """
    img = img.astype(np.float32)
    size = img.shape[0]

    # Segment the lesion: pixels sufficiently different from the estimated
    # background color (sampled from the image corners).
    corner_px = np.concatenate([
        img[:5, :5].reshape(-1, 3), img[:5, -5:].reshape(-1, 3),
        img[-5:, :5].reshape(-1, 3), img[-5:, -5:].reshape(-1, 3),
    ])
    bg_color = corner_px.mean(axis=0)
    dist = np.linalg.norm(img - bg_color[None, None, :], axis=2)
    mask = dist > 25.0

    area = mask.sum()
    if area < 10:  # essentially no lesion detected (e.g. "healthy" samples)
        return np.array([*bg_color, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

    lesion_px = img[mask]
    color_mean = lesion_px.mean(axis=0)
    color_std = lesion_px.std(axis=0)
    area_fraction = area / mask.size

    mirrored = mask[:, ::-1]
    asymmetry_score = np.logical_xor(mask, mirrored).sum() / area

    mf = mask.astype(np.float32)
    grad_x = np.abs(np.diff(mf, axis=1)).sum()
    grad_y = np.abs(np.diff(mf, axis=0)).sum()
    perimeter = grad_x + grad_y
    border_irregularity = perimeter / np.sqrt(max(area, 1))

    return np.array([
        *color_mean, *color_std, area_fraction, asymmetry_score, border_irregularity,
    ], dtype=np.float32)


FEATURE_NAMES = [
    "lesion_mean_r", "lesion_mean_g", "lesion_mean_b",
    "lesion_std_r", "lesion_std_g", "lesion_std_b",
    "area_fraction", "asymmetry_score", "border_irregularity",
]


def generate_dataset(n_per_class: int = 150, seed: int = 42):
    """Generate a synthetic training set: (X features, y labels, sample images for inspection)."""
    rng = np.random.default_rng(seed)
    X, y, sample_images = [], [], {}
    for cls in CLASSES:
        for i in range(n_per_class):
            img, _ = generate_image(cls, rng)
            X.append(extract_features(img))
            y.append(cls)
            if i == 0:
                sample_images[cls] = img
    return np.array(X, dtype=np.float32), np.array(y), sample_images
