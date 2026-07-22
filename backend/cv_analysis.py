"""
Counterfeit Currency Identification Agent - computer vision heuristics.

This is a prototype-grade image analysis pipeline (no proprietary trained
model / genuine-note dataset is available in this environment). Instead of
faking a black-box "genuine/fake" flag, every check below is a real,
inspectable image-processing signal that mirrors the physical checks the
brief calls out:

  1. Print quality / sharpness  -> Laplacian variance (blur & re-print scans
     have low high-frequency energy; genuine intaglio printing is crisp).
  2. Microprint / fine-texture density -> FFT high-frequency energy ratio in
     a central crop (genuine notes carry dense fine-line microprint; photo-
     copies and colour-scans smear this detail).
  3. Security-thread signature -> Hough line detection tuned for a thin,
     near-vertical embedded line (RBI notes carry a windowed security
     thread running top-to-bottom).
  4. Colour-consistency -> compares the dominant hue distribution against
     the expected banded palette for the declared denomination.
  5. Edge-density -> overall Canny edge density as a coarse counterfeit
     "flatness" signal (colour photocopies tend to have fewer, blockier
     edges than genuine multi-process printing).

Each signal is normalised to 0-1 and combined into a weighted authenticity
score. This is intentionally transparent and tunable rather than a black
box, and is clearly labelled as a heuristic prototype in the API response.
"""

import cv2
import numpy as np

# Expected dominant hue bands (OpenCV HSV, H in 0-179) for common INR notes.
# These are rough approximations of the printed base colour, used only as a
# coarse plausibility check.
DENOMINATION_HUE_BANDS = {
    "10": (20, 40),    # chocolate brown
    "20": (18, 34),    # yellow-orange / fluorescent green-ish new series
    "50": (10, 25),    # fluorescent blue/grey - fallback wide band
    "100": (95, 140),  # lavender/grey
    "200": (10, 30),   # bright yellow
    "500": (10, 30),   # stone grey/gold
    "2000": (10, 35),  # magenta/pink (kept for legacy notes)
    "auto": (0, 179),  # skip check
}


def _read_image(image_bytes):
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Please upload a JPEG or PNG.")
    return img


def _sharpness_score(gray):
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    # Empirically, clean smartphone photos of printed notes land ~150-800.
    # Blurry photocopies / heavily compressed scans sit lower.
    score = np.clip(lap_var / 400.0, 0, 1)
    return float(score), float(lap_var)


def _microprint_density(gray):
    h, w = gray.shape
    cy, cx = h // 2, w // 2
    half = min(h, w) // 4
    crop = gray[max(0, cy - half):cy + half, max(0, cx - half):cx + half]
    if crop.size == 0:
        crop = gray
    f = np.fft.fft2(crop)
    fshift = np.fft.fftshift(f)
    magnitude = np.abs(fshift)
    ch, cw = magnitude.shape
    cy2, cx2 = ch // 2, cw // 2
    radius = min(ch, cw) // 6
    y, x = np.ogrid[:ch, :cw]
    mask_high = (x - cx2) ** 2 + (y - cy2) ** 2 > radius ** 2
    high_energy = magnitude[mask_high].sum()
    total_energy = magnitude.sum() + 1e-6
    ratio = high_energy / total_energy
    # Typical genuine crisp print -> ratio ~0.35-0.55; flat/smeared -> lower
    score = np.clip((ratio - 0.15) / 0.35, 0, 1)
    return float(score), float(ratio)


def _security_thread_signature(gray):
    h, w = gray.shape
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=60,
        minLineLength=int(h * 0.35), maxLineGap=8
    )
    near_vertical = 0
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            dx, dy = x2 - x1, y2 - y1
            if abs(dx) < 1e-6:
                angle = 90.0
            else:
                angle = abs(np.degrees(np.arctan2(dy, dx)))
            if 75 <= angle <= 105:
                near_vertical += 1
    # 1-6 clean vertical strokes is consistent with a single embedded thread;
    # 0 suggests it's missing, a very high count usually means paper texture
    # noise rather than a genuine signature.
    if near_vertical == 0:
        score = 0.15
    elif near_vertical > 25:
        score = 0.4
    else:
        score = float(np.clip(near_vertical / 6.0, 0.3, 1.0))
    return score, int(near_vertical)


def _colour_consistency(img, denomination):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0], None, [180], [0, 180]).flatten()
    dominant_hue = int(np.argmax(hist))
    band = DENOMINATION_HUE_BANDS.get(str(denomination), DENOMINATION_HUE_BANDS["auto"])
    if band == (0, 179):
        return 0.75, dominant_hue  # no check requested / unknown denomination
    lo, hi = band
    if lo <= dominant_hue <= hi:
        score = 1.0
    else:
        dist = min(abs(dominant_hue - lo), abs(dominant_hue - hi))
        score = float(np.clip(1 - dist / 40.0, 0.1, 0.9))
    return score, dominant_hue


def _edge_density(gray):
    edges = cv2.Canny(gray, 60, 160)
    density = edges.mean() / 255.0
    # Genuine notes with fine printing typically show moderate-high density.
    score = float(np.clip(density / 0.12, 0, 1))
    return score, float(density)


def analyze_note(image_bytes, denomination="auto"):
    img = _read_image(image_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    sharpness_score, lap_var = _sharpness_score(gray)
    microprint_score, fft_ratio = _microprint_density(gray)
    thread_score, thread_lines = _security_thread_signature(gray)
    colour_score, dominant_hue = _colour_consistency(img, denomination)
    edge_score, edge_density = _edge_density(gray)

    weights = {
        "print_quality": 0.28,
        "microprint_density": 0.27,
        "security_thread": 0.22,
        "colour_consistency": 0.13,
        "edge_density": 0.10,
    }
    components = {
        "print_quality": sharpness_score,
        "microprint_density": microprint_score,
        "security_thread": thread_score,
        "colour_consistency": colour_score,
        "edge_density": edge_score,
    }
    authenticity_score = sum(components[k] * weights[k] for k in weights)
    authenticity_pct = round(authenticity_score * 100, 1)

    if authenticity_pct >= 75:
        verdict = "Likely Genuine"
        alert_level = "low"
    elif authenticity_pct >= 50:
        verdict = "Inconclusive - Manual Verification Recommended"
        alert_level = "medium"
    else:
        verdict = "Suspected Counterfeit"
        alert_level = "high"

    return {
        "verdict": verdict,
        "alert_level": alert_level,
        "authenticity_score": authenticity_pct,
        "denomination_checked": denomination,
        "features": {
            "print_quality": {
                "score": round(sharpness_score * 100, 1),
                "raw_laplacian_variance": round(lap_var, 1),
                "note": "Measures print sharpness. Genuine intaglio printing is crisp; "
                         "photocopies/scans blur fine lines.",
            },
            "microprint_density": {
                "score": round(microprint_score * 100, 1),
                "raw_fft_high_freq_ratio": round(fft_ratio, 3),
                "note": "Estimates density of fine-line microprint via frequency analysis.",
            },
            "security_thread": {
                "score": round(thread_score * 100, 1),
                "vertical_line_signatures_detected": thread_lines,
                "note": "Looks for a single clean embedded vertical thread signature.",
            },
            "colour_consistency": {
                "score": round(colour_score * 100, 1),
                "dominant_hue": dominant_hue,
                "note": "Checks dominant colour band against the expected note palette.",
            },
            "edge_density": {
                "score": round(edge_score * 100, 1),
                "raw_edge_density": round(edge_density, 4),
                "note": "Coarse texture/flatness signal from edge density.",
            },
        },
        "weights_used": weights,
        "disclaimer": (
            "Prototype heuristic CV pipeline for demo purposes only - not a certified "
            "currency-verification system. Do not use as sole basis for a real "
            "counterfeit determination."
        ),
    }
