"""Visualisation helpers for spectral (frequency-domain) HRV analysis.

Five public functions cover the core frequency-domain views:

* :func:`plot_psd_welch`        — PSD with VLF/LF/HF bands filled in colour.
* :func:`plot_psd_comparison`   — AR vs Welch PSD curves overlaid on the same axis.
* :func:`plot_lf_hf_evolution`  — LF/HF balance (grouped bars) across sessions.
* :func:`plot_hrv_radar`        — Radar chart of 5 normalised HRV metrics.
* :func:`plot_spectral_heatmap` — Sessions × frequency-band power heatmap.
"""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from cardiolab.features.frequency_domain import _ar_psd as _ar_psd_raw
from cardiolab.features.frequency_domain import _band_power, _interpolate
from cardiolab.features.frequency_domain import _welch_psd as _welch_psd_raw
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.signals.rr import RRSeries

# ── Colour palette ───────────────────────────────────────────────────────────

_VLF_COLOR = "#8e44ad"
_LF_COLOR = "#2980b9"
_HF_COLOR = "#27ae60"
_AR_COLOR = "#e74c3c"
_DARK = "#2c3e50"
_GRAY = "#95a5a6"

_PALETTE = [
    "#2980b9",
    "#27ae60",
    "#e74c3c",
    "#f39c12",
    "#8e44ad",
    "#16a085",
    "#d35400",
    "#7f8c8d",
]

# ── Band definitions ─────────────────────────────────────────────────────────

_VLF_BAND = (0.003, 0.04)
_LF_BAND = (0.04, 0.15)
_HF_BAND = (0.15, 0.40)

# ── Radar normalisation ranges (min, max) ────────────────────────────────────
# Each tuple defines the reference range used to scale 0 → 1.
# Values outside the range are clipped.

_RADAR_METRICS: list[tuple[str, str, float, float]] = [
    ("rmssd", "RMSSD\n(ms)", 0.0, 100.0),
    ("lf_nu", "LF_nu", 0.0, 1.0),
    ("hf_nu", "HF_nu", 0.0, 1.0),
    ("sd1", "SD1\n(ms)", 0.0, 70.0),
    ("dfa_alpha1", "DFA α1", 0.0, 1.5),
]


# ── Private helpers (signal-level) ──────────────────────────────────────────
# _interpolate, _welch_psd (raw), _ar_psd (raw), _band_power are imported
# from cardiolab.features.frequency_domain above.
# The two wrappers below accept RRSeries and delegate after interpolation.


def _welch_psd(rr: RRSeries, fs: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(freqs, psd)`` via Welch's method for an RRSeries input."""
    _, signal = _interpolate(rr, fs)
    return _welch_psd_raw(signal, fs)


def _ar_psd(
    rr: RRSeries, fs: float = 4.0, order: int = 16
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(freqs, psd)`` via the Yule-Walker AR method for an RRSeries input."""
    _, signal = _interpolate(rr, fs)
    return _ar_psd_raw(signal, fs=fs, order=order)


def _fill_bands(
    ax: plt.Axes, freqs: np.ndarray, psd: np.ndarray, alpha: float = 0.35
) -> dict[str, float]:
    """Fill VLF/LF/HF coloured areas; return a dict of band powers."""
    powers: dict[str, float] = {}
    for band_label, (low, high), color in [
        ("VLF", _VLF_BAND, _VLF_COLOR),
        ("LF", _LF_BAND, _LF_COLOR),
        ("HF", _HF_BAND, _HF_COLOR),
    ]:
        mask = (freqs >= low) & (freqs < high)
        powers[band_label] = _band_power(freqs, psd, low, high)
        if mask.any():
            ax.fill_between(
                freqs, psd, where=mask, alpha=alpha, color=color, label=band_label
            )
    return powers


def _draw_band_boundaries(ax: plt.Axes) -> None:
    """Draw dotted vertical lines at VLF/LF/HF boundaries."""
    for x in (0.04, 0.15, 0.40):
        ax.axvline(x, color=_GRAY, linewidth=0.8, linestyle=":", alpha=0.7)


def _annotate_powers(ax: plt.Axes, powers: dict[str, float]) -> None:
    """Add a text box with band power values."""
    lines = [
        f"VLF: {powers.get('VLF', 0):.0f} ms²",
        f"LF:  {powers.get('LF',  0):.0f} ms²",
        f"HF:  {powers.get('HF',  0):.0f} ms²",
    ]
    ax.text(
        0.97,
        0.97,
        "\n".join(lines),
        transform=ax.transAxes,
        fontsize=8,
        va="top",
        ha="right",
        bbox={
            "boxstyle": "round,pad=0.4",
            "facecolor": "white",
            "alpha": 0.85,
            "edgecolor": _GRAY,
        },
    )


def _label_bands(ax: plt.Axes, y_top: float) -> None:
    """Place text labels in the centre of each frequency band."""
    for x_mid, label in [
        (0.021, "VLF"),
        (0.095, "LF"),
        (0.275, "HF"),
    ]:
        ax.text(
            x_mid,
            y_top * 0.92,
            label,
            fontsize=9,
            ha="center",
            color=_DARK,
            alpha=0.65,
            fontweight="bold",
        )


def _safe_norm(value: float, vmin: float, vmax: float) -> float:
    """Normalise a value to [0, 1]; replace NaN with 0."""
    if math.isnan(value) or vmax <= vmin:
        return 0.0
    return float(np.clip((value - vmin) / (vmax - vmin), 0.0, 1.0))


# ── Public functions ─────────────────────────────────────────────────────────


def plot_psd_welch(
    rr: RRSeries,
    title: str = "Power Spectral Density",
    method: str = "welch",
    order: int = 16,
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot the RR power spectral density with VLF, LF, and HF bands coloured.

    The PSD is estimated either by Welch's method (default) or the Yule-Walker
    AR method.  The three physiological frequency bands are filled in colour:
    VLF (violet), LF (blue), HF (green).  Band power values (ms²) are annotated
    in a legend box.

    Args:
        rr: RR interval series.
        title: Figure title (the method name is appended automatically).
        method: PSD estimation method — ``"welch"`` or ``"ar"``.
        order: AR model order (used only when ``method="ar"``).
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` is not an :class:`~cardiolab.signals.rr.RRSeries`.
        ValueError: If ``method`` is not ``"welch"`` or ``"ar"``.
        ValueError: If ``order`` < 1.

    """
    if not isinstance(rr, RRSeries):
        raise TypeError(f"rr must be an RRSeries, got {type(rr).__name__}")
    if method not in ("welch", "ar"):
        raise ValueError(f"method must be 'welch' or 'ar', got {method!r}")
    if order < 1:
        raise ValueError(f"order must be >= 1, got {order}")

    freqs, psd = _welch_psd(rr) if method == "welch" else _ar_psd(rr, order=order)

    fig, ax = plt.subplots(figsize=figsize)

    ax.plot(freqs, psd, color=_DARK, linewidth=1.2, alpha=0.9, zorder=4)
    powers = _fill_bands(ax, freqs, psd)
    _draw_band_boundaries(ax)
    _annotate_powers(ax, powers)

    y_top = float(psd[(freqs >= 0.003) & (freqs <= 0.40)].max()) if len(psd) else 1.0
    _label_bands(ax, y_top)

    ax.set_xlim(0, 0.45)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Frequency (Hz)", fontsize=10)
    ax.set_ylabel("PSD (ms²/Hz)", fontsize=10)
    ax.set_title(f"{title}  [{method.upper()}]", fontsize=12, fontweight="bold", pad=10)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.20, linestyle=":")

    plt.tight_layout()
    return fig


def plot_psd_comparison(
    rr: RRSeries,
    title: str = "PSD Comparison — Welch vs AR",
    order: int = 16,
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Overlay Welch and AR PSD curves on the same axis.

    Both methods are computed from the same interpolated RR series and drawn
    on top of the same VLF/LF/HF coloured band fills (computed from the Welch
    estimate).  The AR curve uses a dashed red line so differences in spectral
    resolution and peak sharpness are immediately visible.

    Args:
        rr: RR interval series.
        title: Figure title.
        order: AR model order.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` is not an :class:`~cardiolab.signals.rr.RRSeries`.
        ValueError: If ``order`` < 1.

    """
    if not isinstance(rr, RRSeries):
        raise TypeError(f"rr must be an RRSeries, got {type(rr).__name__}")
    if order < 1:
        raise ValueError(f"order must be >= 1, got {order}")

    freqs_w, psd_w = _welch_psd(rr)
    freqs_ar, psd_ar = _ar_psd(rr, order=order)

    fig, ax = plt.subplots(figsize=figsize)

    powers = _fill_bands(ax, freqs_w, psd_w, alpha=0.25)
    ax.plot(
        freqs_w,
        psd_w,
        color=_LF_COLOR,
        linewidth=1.4,
        alpha=0.9,
        label="Welch",
        zorder=4,
    )
    ax.plot(
        freqs_ar,
        psd_ar,
        color=_AR_COLOR,
        linewidth=1.4,
        linestyle="--",
        alpha=0.9,
        label=f"AR (order {order})",
        zorder=5,
    )
    _draw_band_boundaries(ax)
    _annotate_powers(ax, powers)

    y_top = float(
        max(
            psd_w[(freqs_w >= 0.003) & (freqs_w <= 0.40)].max() if len(psd_w) else 1.0,
            psd_ar[(freqs_ar >= 0.003) & (freqs_ar <= 0.40)].max()
            if len(psd_ar)
            else 1.0,
        )
    )
    _label_bands(ax, y_top)

    ax.set_xlim(0, 0.45)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Frequency (Hz)", fontsize=10)
    ax.set_ylabel("PSD (ms²/Hz)", fontsize=10)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(alpha=0.20, linestyle=":")

    plt.tight_layout()
    return fig


def plot_lf_hf_evolution(
    features_list: list[HRVFeatures],
    labels: list[str] | None = None,
    title: str = "LF/HF Balance Evolution",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot grouped bars showing LF/HF autonomic balance across sessions.

    Each session is represented by two adjacent bars (LF_nu in blue, HF_nu in
    green).  Because LF_nu + HF_nu = 1, the two bars are complementary and
    directly show the autonomic balance.  The LF/HF ratio is overlaid as a red
    line on a secondary y-axis.

    Args:
        features_list: List of :class:`~cardiolab.protocols.resting.HRVFeatures`
            objects, one per session, in chronological order.
        labels: Session labels.  Falls back to ``"Session N"`` if not provided.
        title: Figure title.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``features_list`` is not a list or contains non-HRVFeatures
            elements.
        ValueError: If ``features_list`` is empty.
        ValueError: If ``labels`` is provided with a length that differs from
            ``features_list``.

    """
    if not isinstance(features_list, list):
        raise TypeError(
            f"features_list must be a list, got {type(features_list).__name__}"
        )
    if len(features_list) == 0:
        raise ValueError("features_list must contain at least one HRVFeatures.")
    for idx, item in enumerate(features_list):
        if not isinstance(item, HRVFeatures):
            raise TypeError(
                f"features_list[{idx}] must be an HRVFeatures, "
                f"got {type(item).__name__}"
            )
    if labels is not None and len(labels) != len(features_list):
        raise ValueError(
            f"labels length ({len(labels)}) must match features_list length "
            f"({len(features_list)})"
        )

    if labels is None:
        labels = [
            str(f.date) if f.date else f"Session {i + 1}"
            for i, f in enumerate(features_list)
        ]

    n = len(features_list)
    lf_nu = np.array([f.lf_nu for f in features_list])
    hf_nu = np.array([f.hf_nu for f in features_list])
    lf_hf = np.array([f.lf_hf for f in features_list])

    x = np.arange(n)
    bar_w = 0.35

    fig, ax = plt.subplots(figsize=figsize)

    bars_lf = ax.bar(
        x - bar_w / 2,
        lf_nu,
        width=bar_w,
        color=_LF_COLOR,
        alpha=0.75,
        label="LF_nu",
    )
    bars_hf = ax.bar(
        x + bar_w / 2,
        hf_nu,
        width=bar_w,
        color=_HF_COLOR,
        alpha=0.75,
        label="HF_nu",
    )

    # Value annotations
    for bar in bars_lf:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + 0.01,
            f"{h:.2f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color=_LF_COLOR,
        )
    for bar in bars_hf:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + 0.01,
            f"{h:.2f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color=_HF_COLOR,
        )

    ax.set_ylim(0, 1.15)
    ax.axhline(0.5, color=_GRAY, linewidth=0.8, linestyle=":", alpha=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=9)
    ax.set_ylabel("Normalised units (LF_nu / HF_nu)", fontsize=10)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(axis="y", alpha=0.20, linestyle=":")

    # LF/HF ratio on secondary axis
    ax2 = ax.twinx()
    ax2.plot(
        x,
        lf_hf,
        color=_AR_COLOR,
        linewidth=1.5,
        marker="D",
        markersize=5,
        label="LF/HF ratio",
        zorder=5,
    )
    ax2.axhline(1.0, color=_AR_COLOR, linewidth=0.7, linestyle=":", alpha=0.5)
    ax2.set_ylabel("LF/HF ratio", fontsize=10, color=_AR_COLOR)
    ax2.tick_params(axis="y", colors=_AR_COLOR, labelsize=8)
    ax2.legend(loc="upper right", fontsize=9)

    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    plt.tight_layout()
    return fig


def plot_hrv_radar(
    features: HRVFeatures,
    title: str = "HRV Radar Profile",
    figsize: tuple[float, float] = (7, 7),
) -> Figure:
    """Radar (spider) chart of five normalised HRV metrics.

    The five axes are RMSSD, LF_nu, HF_nu, SD1, and DFA α1, each normalised
    against a physiological reference range so that a value near 1 corresponds
    to the upper end of the healthy resting range.  NaN values (e.g. DFA α1
    on very short recordings) are plotted at zero with a warning annotation.

    Reference ranges used for normalisation:

    * RMSSD : 0 – 100 ms
    * LF_nu : 0 – 1.0
    * HF_nu : 0 – 1.0
    * SD1    : 0 – 70 ms
    * DFA α1 : 0 – 1.5

    Args:
        features: A single :class:`~cardiolab.protocols.resting.HRVFeatures`
            session to profile.
        title: Figure title.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``features`` is not an
            :class:`~cardiolab.protocols.resting.HRVFeatures`.

    """
    if not isinstance(features, HRVFeatures):
        raise TypeError(
            f"features must be an HRVFeatures, got {type(features).__name__}"
        )

    metric_keys = [m[0] for m in _RADAR_METRICS]
    metric_labels = [m[1] for m in _RADAR_METRICS]
    raw_values = [getattr(features, k) for k in metric_keys]

    # Normalise each value to [0, 1]
    norm_values = [
        _safe_norm(v, vmin, vmax)
        for v, (_, _, vmin, vmax) in zip(raw_values, _RADAR_METRICS, strict=False)
    ]
    has_nan = any(math.isnan(getattr(features, k)) for k in metric_keys)

    # Close the polygon
    n = len(_RADAR_METRICS)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]
    norm_values_closed = norm_values + norm_values[:1]

    fig, ax = plt.subplots(figsize=figsize, subplot_kw={"polar": True})

    # Reference rings — angles already closed (n+1 elements)
    for level in (0.25, 0.5, 0.75, 1.0):
        ax.plot(
            angles,
            [level] * len(angles),
            color=_GRAY,
            linewidth=0.5,
            linestyle=":",
            alpha=0.5,
        )
    ax.fill(angles, [1.0] * len(angles), color=_GRAY, alpha=0.06)

    # Data polygon
    ax.plot(
        angles, norm_values_closed, color=_LF_COLOR, linewidth=2.0, zorder=4
    )
    ax.fill(
        angles, norm_values_closed, color=_LF_COLOR, alpha=0.20
    )
    ax.scatter(
        angles[:-1], norm_values, color=_LF_COLOR, s=50, zorder=5
    )

    # Labels with raw values
    ax.set_thetagrids(
        np.degrees(angles[:-1]),
        labels=[
            f"{label}\n{v:.2g}"
            for label, v in zip(metric_labels, raw_values, strict=False)
        ],
        fontsize=9,
    )
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0.25, 0.5, 0.75])
    ax.set_yticklabels(["25 %", "50 %", "75 %"], fontsize=7, color=_GRAY)
    ax.grid(color=_GRAY, linewidth=0.4, alpha=0.5)

    suffix = " ⚠ NaN values set to 0" if has_nan else ""
    session_id = str(features.date) if features.date else ""
    full_title = f"{title}\n{session_id}{suffix}" if session_id else title + suffix
    ax.set_title(full_title, fontsize=11, fontweight="bold", pad=20)

    plt.tight_layout()
    return fig


def plot_spectral_heatmap(
    features_list: list[HRVFeatures],
    labels: list[str] | None = None,
    title: str = "Spectral Power Heatmap — Sessions × Bands",
    normalize: bool = True,
    figsize: tuple[float, float] = (12, 0.6),
) -> Figure:
    """Heatmap of frequency-band powers across sessions.

    Rows represent sessions (chronological order from bottom to top), columns
    represent six spectral metrics: VLF, LF, HF (absolute power in ms²), then
    LF/HF, LF_nu, and HF_nu (dimensionless ratios).

    When ``normalize=True`` (default), each column is rescaled to [0, 1] using
    per-column min-max normalisation, making it easy to spot relative changes
    within each band across sessions.  Absolute values are annotated inside
    each cell.

    Args:
        features_list: List of
            :class:`~cardiolab.protocols.resting.HRVFeatures`, one per session.
        labels: Session labels.  Falls back to date strings or ``"Session N"``.
        title: Figure title.
        normalize: Whether to apply per-column min-max normalisation.
        figsize: ``(width, height_per_session)`` — total height is
            ``figsize[1] × n_sessions``, clamped to at least 4 inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If any element of ``features_list`` is not an
            :class:`~cardiolab.protocols.resting.HRVFeatures`.
        ValueError: If ``features_list`` is empty.
        ValueError: If ``labels`` is provided with a mismatched length.

    """
    if not isinstance(features_list, list):
        raise TypeError(
            f"features_list must be a list, got {type(features_list).__name__}"
        )
    if len(features_list) == 0:
        raise ValueError("features_list must contain at least one HRVFeatures.")
    for idx, item in enumerate(features_list):
        if not isinstance(item, HRVFeatures):
            raise TypeError(
                f"features_list[{idx}] must be an HRVFeatures, "
                f"got {type(item).__name__}"
            )
    if labels is not None and len(labels) != len(features_list):
        raise ValueError(
            f"labels length ({len(labels)}) must match features_list length "
            f"({len(features_list)})"
        )

    if labels is None:
        labels = [
            str(f.date) if f.date else f"Session {i + 1}"
            for i, f in enumerate(features_list)
        ]

    # Build data matrix: rows = sessions, columns = bands
    col_names = ["VLF\n(ms²)", "LF\n(ms²)", "HF\n(ms²)", "LF/HF", "LF_nu", "HF_nu"]
    attr_names = ["vlf", "lf", "hf", "lf_hf", "lf_nu", "hf_nu"]

    data = np.array(
        [[getattr(f, a) for a in attr_names] for f in features_list],
        dtype=float,
    )

    # Per-column min-max normalisation
    if normalize and len(features_list) >= 2:
        col_min = data.min(axis=0)
        col_max = data.max(axis=0)
        span = col_max - col_min
        span[span == 0] = 1.0
        data_display = (data - col_min) / span
    else:
        data_display = data.copy()

    n_sessions, n_cols = data.shape
    total_h = max(4.0, figsize[1] * n_sessions)
    fig, ax = plt.subplots(figsize=(figsize[0], total_h))

    im = ax.imshow(
        data_display,
        aspect="auto",
        cmap="RdYlGn",
        vmin=0,
        vmax=1 if normalize else None,
        interpolation="nearest",
    )

    # Cell annotations: raw values
    for row in range(n_sessions):
        for col in range(n_cols):
            val = data[row, col]
            cell_val = data_display[row, col]
            text_color = "white" if cell_val < 0.25 or cell_val > 0.80 else _DARK
            fmt = f"{val:.0f}" if col < 3 else f"{val:.2f}"
            ax.text(
                col,
                row,
                fmt,
                ha="center",
                va="center",
                fontsize=8,
                color=text_color,
                fontweight="bold",
            )

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(col_names, fontsize=9)
    ax.set_yticks(range(n_sessions))
    ax.set_yticklabels(labels, fontsize=9)
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.04)
    cbar.set_label(
        "Normalised value (per column)" if normalize else "Raw value",
        fontsize=8,
    )
    cbar.ax.tick_params(labelsize=7)

    ax.set_title(
        title,
        fontsize=12,
        fontweight="bold",
        pad=30,
    )

    plt.tight_layout()
    return fig
