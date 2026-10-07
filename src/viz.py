"""Shared chart style so every notebook chart looks like part of one system.

Palette: a colour-blind-validated categorical order (blue, orange, aqua, yellow, ...).
Rule: colour follows the ENTITY, never its rank. Paid Social is always orange,
Paid Search always blue; other channels are grey unless a chart is about them.
"""
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
GREY, GREY_LIGHT, INK, INK_2 = "#8a8984", "#d6d5d0", "#0b0b0b", "#52514e"

CHANNEL_COLORS = {
    "Paid Search": BLUE, "Paid Social": ORANGE, "Organic Search": AQUA, "Direct": VIOLET,
    "Affiliate": YELLOW, "Email": MAGENTA, "Organic Social": GREEN, "Referral": RED,
    "Unattributed": GREY,
}
DEVICE_COLORS = {"mobile": ORANGE, "desktop": BLUE, "tablet": AQUA}
SEQ_BLUE = LinearSegmentedColormap.from_list(
    "seq_blue", ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])


def setup():
    plt.rcParams.update({
        "figure.figsize": (9, 4), "figure.dpi": 100, "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": GREY_LIGHT, "axes.labelcolor": INK_2, "axes.titlesize": 12,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlecolor": INK,
        "axes.grid": True, "grid.color": "#ecebe7", "grid.linewidth": 0.8,
        "xtick.color": INK_2, "ytick.color": INK_2, "legend.frameon": False,
        "lines.linewidth": 2,
    })


def highlight(channel, focus=("Paid Social", "Paid Search")):
    """Colour for a channel in a 'highlight' chart: focus channels coloured, rest grey."""
    return CHANNEL_COLORS.get(channel, GREY) if channel in focus else GREY_LIGHT


def inr(x, _=None):
    """Axis formatter: 1,234 -> ₹1.2k ; 1,234,567 -> ₹12.3L (lakh)."""
    if abs(x) >= 1e5:
        return f"₹{x / 1e5:.1f}L"
    if abs(x) >= 1e3:
        return f"₹{x / 1e3:.1f}k"
    return f"₹{x:.0f}"


def spread_labels(values, min_gap):
    """Return label y-positions near `values` but at least `min_gap` apart (for end-of-line labels)."""
    import numpy as np
    order = np.argsort(values)
    pos = np.array(values, dtype=float)[order]
    for i in range(1, len(pos)):
        pos[i] = max(pos[i], pos[i - 1] + min_gap)
    out = np.empty_like(pos)
    out[order] = pos
    return out
