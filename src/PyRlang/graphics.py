"""R-flavoured plotting on matplotlib (optional): plot(), hist(), barplot().

Figures are saved as PNG in the working directory and the path is printed,
which keeps the pure-Python core dependency-free: matplotlib is used when
installed and a clear error is raised when not.
"""

from __future__ import annotations

import os
import sys

from PyRlang.vector import NA, PyRError, Vector

__all__ = ["barplot", "hist", "plot"]

_PLT = None
_FIG_NO = 0


def _pyplot():
    global _PLT
    if _PLT is None:
        try:
            import matplotlib
            import matplotlib.pyplot as plt
        except ImportError:
            raise PyRError("plot features need matplotlib: pip install matplotlib") from None
        if "DISPLAY" not in os.environ and sys.platform != "darwin":
            try:
                matplotlib.use("Agg")
            except Exception:  # noqa: BLE001 - backend choice is best-effort
                pass
        _PLT = plt
    return _PLT


def _values_of(x, kind):
    if isinstance(x, Vector):
        vals = [v for v in x.data if v is not NA]
    elif isinstance(x, (list, tuple)):
        vals = [v for v in x if v is not NA]
    elif isinstance(x, bool):
        vals = [1 if x else 0]
    elif isinstance(x, (int, float)):
        vals = [x]
    else:
        raise PyRError(f"{kind}() expects a numeric vector")
    out = []
    for v in vals:
        if isinstance(v, bool):
            out.append(int(v))
        elif isinstance(v, (int, float)):
            out.append(v)
        else:
            raise PyRError(f"{kind}() expects a numeric vector")
    return out


def _save(fig, kind):
    global _FIG_NO
    _FIG_NO += 1
    name = f"{kind}_{_FIG_NO:02d}.png"
    fig.savefig(name, dpi=150, bbox_inches="tight")
    print(f"Plot saved to {name}")
    return fig


def plot(x, y=None, type: str = "p", main=None, xlab=None, ylab=None, col=None):
    """Scatter or line plot of (x, y); y defaults to 1..n like R's plot(x)."""
    plt = _pyplot()
    xs = _values_of(x, "plot")
    if y is None:
        ys, xs = xs, list(range(1, len(xs) + 1))
    else:
        ys = _values_of(y, "plot")
    fig, ax = plt.subplots()
    if type == "l":
        ax.plot(xs, ys, color=col)
    elif type == "b" or type == "o":
        ax.plot(xs, ys, marker="o", color=col)
    else:
        ax.scatter(xs, ys, color=col)
    if main is not None:
        ax.set_title(str(main))
    ax.set_xlabel(str(xlab) if xlab is not None else "Index")
    ax.set_ylabel(str(ylab) if ylab is not None else "x")
    return _save(fig, "plot")


def hist(x, breaks: int = 10, main=None, xlab=None, col=None):
    """Histogram of a numeric vector (like R's hist())."""
    plt = _pyplot()
    vals = _values_of(x, "hist")
    if not vals:
        raise PyRError("hist() expects a non-empty numeric vector")
    fig, ax = plt.subplots()
    ax.hist(vals, bins=int(breaks), color=col, edgecolor="black", linewidth=0.5)
    if main is not None:
        ax.set_title(str(main))
    ax.set_xlabel(str(xlab) if xlab is not None else "x")
    return _save(fig, "hist")


def barplot(height, names_arg=None, main=None, xlab=None, ylab=None, col=None):
    """Bar chart of heights with optional names (R's names.arg)."""
    plt = _pyplot()
    vals = _values_of(height, "barplot")
    if names_arg is None:
        labels = [str(i + 1) for i in range(len(vals))]
    elif isinstance(names_arg, Vector):
        labels = [str(v) for v in names_arg.data if v is not NA]
    else:
        labels = [str(n) for n in names_arg]
    fig, ax = plt.subplots()
    ax.bar(range(len(vals)), vals, color=col, tick_label=labels)
    if main is not None:
        ax.set_title(str(main))
    if xlab is not None:
        ax.set_xlabel(str(xlab))
    if ylab is not None:
        ax.set_ylabel(str(ylab))
    return _save(fig, "barplot")
