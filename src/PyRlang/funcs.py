"""The R-flavoured function library: vectors, statistics, strings, pipes.

Everything here is importable from plain Python after ``from PyRlang import *``
and is pre-bound into the namespace of ``.pyr`` scripts and the REPL.
Names like ``min``, ``max``, ``sum``, ``sort`` and ``cat`` intentionally
shadow the Python builtins with R-flavoured versions inside PyRlang scopes.
"""

from __future__ import annotations

import math
import sys

import PyRlang.vector as _vec
from PyRlang.dataframe import DataFrame
from PyRlang.formula import Formula
from PyRlang.vector import (
    NA,
    PyRError,
    Vector,
    _np_bridge,
    _np_view,
    _r_lnot,
    fmt_value,
    format_number,
    is_scalar,
)

# R-flavoured min/max/sum below shadow the Python builtins inside this module,
# so keep the builtins under aliases for internal plumbing.
_py_max = max
_py_min = min
_py_sum = sum


def _has_numpy():
    """Read the live backend flag (tests may switch it off at runtime)."""
    return _vec._np is not None


__all__ = [
    "Summary",
    "SummaryMulti",
    "Table",
    "c",
    "cat",
    "data_frame",
    "exp",
    "head",
    "ifelse",
    "isin",
    "length",
    "log",
    "log10",
    "log2",
    "max",
    "mean",
    "median",
    "min",
    "nchar",
    "ncol",
    "names",
    "not_",
    "nrow",
    "paste",
    "paste0",
    "pipe",
    "prod",
    "q",
    "source",
    "rep",
    "rev",
    "sd",
    "seq",
    "sort",
    "sprintf",
    "sqrt",
    "substring",
    "substr",
    "sum",
    "summary",
    "table",
    "tail",
    "tolower",
    "toupper",
    "unique",
    "var",
    "which",
    "which_max",
    "which_min",
]

# -- value handling -----------------------------------------------------------


def _values(x):
    """Flatten like R's ``c()``; ``None`` (NULL) contributes nothing."""
    if x is None:
        return []
    if isinstance(x, Vector):
        return list(x.data)
    if isinstance(x, range):
        return list(x)
    if isinstance(x, (list, tuple)):
        out = []
        for item in x:
            out.extend(_values(item))
        return out
    if is_scalar(x):
        return [x]
    raise PyRError(f"cannot coerce {type(x).__name__} into a vector")


def _unify(vals):
    """R's coercion hierarchy: string > double > integer > logical."""
    if any(v is not NA and isinstance(v, str) for v in vals):
        out = []
        for v in vals:
            if v is NA:
                out.append(NA)
            elif isinstance(v, str):
                out.append(v)
            elif isinstance(v, bool):
                out.append("TRUE" if v else "FALSE")
            elif isinstance(v, float):
                out.append(format_number(v))
            elif isinstance(v, int):
                out.append(str(v))
            else:
                out.append(str(v))
        return out
    if any(v is not NA and isinstance(v, float) for v in vals):
        return [int(v) if isinstance(v, bool) else v for v in vals]
    return list(vals)


def _flatten_args(args):
    if len(args) == 1 and isinstance(args[0], (Vector, list, tuple)):
        return _values(args[0])
    out = []
    for a in args:
        out.extend(_values(a))
    return out


def _numeric(x, who, na_rm: bool):
    vals = _values(x)
    out = []
    for v in vals:
        if v is NA:
            out.append(NA)
        elif isinstance(v, bool):
            out.append(int(v))
        elif isinstance(v, (int, float)):
            out.append(v)
        else:
            raise PyRError(f"{who}() requires numeric values")
    if na_rm:
        return [v for v in out if v is not NA]
    if any(v is NA for v in out):
        return [NA]
    return out


def _quantile7(sorted_vals, p):
    if _has_numpy():
        return float(_vec._np.quantile(_vec._np.array(sorted_vals), p))
    n = len(sorted_vals)
    h = (n - 1) * p
    lo = math.floor(h)
    hi = math.ceil(h)
    val = sorted_vals[lo]
    if hi != lo:
        val += (h - lo) * (sorted_vals[hi] - sorted_vals[lo])
    return val


# -- vector constructors --------------------------------------------------------


def c(*args) -> Vector:
    """Combine values into a vector, flattening and coercing like R's ``c()``."""
    vals: list = []
    for a in args:
        vals.extend(_values(a))
    return Vector(_unify(vals))


def seq(*args, to=None, by=None, length_out=None, from_=None) -> Vector:
    """``seq()``: seq(10), seq(1, 10), seq(0, 1, by=0.25), seq(1, 10, length_out=4)."""
    if args:
        if len(args) == 1:
            if from_ is not None:
                raise PyRError("seq(): 'from' given twice")
            to = args[0] if to is None else to
            from_ = 1
        elif len(args) == 2:
            if from_ is not None or to is not None:
                raise PyRError("seq(): too many arguments")
            from_, to = args
        else:
            raise PyRError("seq() takes at most 2 positional arguments")
    else:
        if from_ is None:
            from_ = 1
        if to is None:
            raise PyRError("seq() needs a 'to' value")
    if by is not None and not isinstance(by, (int, float)):
        raise PyRError("seq(): 'by' must be numeric")
    if not isinstance(from_, (int, float)) or not isinstance(to, (int, float)):
        raise PyRError("seq(): 'from' and 'to' must be numeric")
    if isinstance(from_, bool):
        from_ = int(from_)
    if isinstance(to, bool):
        to = int(to)

    if length_out is not None:
        if by is not None:
            raise PyRError("seq(): 'by' and 'length_out' cannot both be given")
        n = int(length_out)
        if n < 0:
            raise PyRError("seq(): 'length_out' must be non-negative")
        if n == 0:
            return Vector([])
        if n == 1:
            return Vector([from_])
        step = (to - from_) / (n - 1)
        vals = [from_ + k * step for k in range(n)]
        if isinstance(from_, int) and float(step).is_integer():
            vals = [int(v) for v in vals]
        return Vector(vals)

    if by is None:
        by = 1 if to >= from_ else -1
    if by == 0:
        raise PyRError("seq(): step of zero")
    if (to - from_) * by < 0:
        return Vector([])
    vals = []
    k = 0
    while True:
        v = from_ + k * by
        if (by > 0 and v > to) or (by < 0 and v < to):
            break
        vals.append(v)
        k += 1
        if k > 10_000_000:
            raise PyRError("seq(): result too long")
    return Vector(vals)


def rep(x, times=None, each=None, length_out=None) -> Vector:
    """``rep()``: repeat the elements of a vector."""
    vals = _values(x)
    if each is not None:
        vals = [v for v in vals for _ in range(int(each))]
    if times is not None:
        vals = vals * int(times)
    if length_out is not None:
        n = int(length_out)
        if n <= 0:
            vals = []
        elif not vals:
            vals = []
        elif len(vals) >= n:
            vals = vals[:n]
        else:
            vals = [vals[k % len(vals)] for k in range(n)]
    return Vector(vals)


# -- inspection -----------------------------------------------------------------


def length(x) -> int:
    """Vector length (a string has length 1, like R)."""
    return len(_values(x))


def unique(x) -> Vector:
    """Unique values, first occurrence kept (like R)."""
    if _has_numpy():
        view = _np_view(_values(x))
        if view is not None:
            arr, mask = view
            uniq, first = _vec._np.unique(arr, return_index=True)
            del uniq
            order = _vec._np.sort(first)
            lst = arr[order].tolist()
            if mask is not None and mask.any():
                m2 = mask[order].tolist()
                lst = [NA if m else v for m, v in zip(m2, lst, strict=True)]
            return Vector(lst)
    out = []
    seen = set()
    for v in _values(x):
        if v is NA:
            if not any(k is NA for k in out):
                out.append(NA)
            continue
        key = (type(v), v)
        if key not in seen:
            seen.add(key)
            out.append(v)
    return Vector(out)


def sort(x, decreasing: bool = False, na_last=None) -> Vector:
    """Sort like R: NA dropped by default, na_last=True appends them."""
    vals = _values(x)
    nas = [v for v in vals if v is NA]
    rest = [v for v in vals if v is not NA]
    if _has_numpy():
        view = _np_view(rest)
        if view is not None:
            srt = _vec._np.sort(view[0], kind="stable")
            rest = list(srt[::-1] if decreasing else srt)
        else:
            try:
                rest = sorted(rest, reverse=decreasing)
            except TypeError as exc:
                raise PyRError(str(exc)) from None
    else:
        try:
            rest = sorted(rest, reverse=decreasing)
        except TypeError as exc:
            raise PyRError(str(exc)) from None
    if na_last is None:
        return Vector(rest)
    if na_last:
        return Vector(rest + nas)
    return Vector(nas + rest)


def rev(x) -> Vector:
    """Reverse element order."""
    return Vector(list(reversed(_values(x))))


def head(x, n=6) -> Vector:
    """First n elements (default 6); a negative n drops the last ones."""
    vals = _values(x)
    n = int(n)
    if n < 0:
        return Vector(vals[: len(vals) + n])
    return Vector(vals[:n])


def tail(x, n=6) -> Vector:
    """Last n elements (default 6); a negative n drops the first ones."""
    vals = _values(x)
    n = int(n)
    if n < 0:
        return Vector(vals[-n:])
    if n == 0:
        return Vector([])
    return Vector(vals[-n:])


def which(x) -> Vector:
    """1-based positions where a logical vector is TRUE (NA treated as no)."""
    vals = _values(x)
    positions = []
    for k, v in enumerate(vals):
        if v is NA:
            continue
        if isinstance(v, bool):
            if v:
                positions.append(k + 1)
        elif isinstance(v, (int, float)):
            if v != 0:
                positions.append(k + 1)
        else:
            raise PyRError("which() expects a logical vector")
    return Vector(positions)


def _argmax(vals, pick):
    best_index = None
    best = None
    for k, v in enumerate(vals):
        if v is NA or isinstance(v, (str,)):
            continue
        if isinstance(v, bool):
            v = int(v)
        if best is None:
            best, best_index = v, k
        elif (v > best) if pick == "max" else (v < best):
            best, best_index = v, k
    if best_index is None:
        raise PyRError("which_max/which_min: no non-NA numeric values")
    return best_index + 1


def which_max(x) -> int:
    """1-based position of the maximum, NA ignored (R's ``which.max``)."""
    return _argmax(_values(x), "max")


def which_min(x) -> int:
    """1-based position of the minimum, NA ignored (R's ``which.min``)."""
    return _argmax(_values(x), "min")


def ifelse(test, yes, no) -> Vector:
    """Vectorised conditional, recycling shorter arguments (like R)."""
    t = _values(test)
    y = _values(yes)
    n_ = _values(no)
    if not t:
        return Vector([])
    total = _py_max(len(t), len(y) if y else 1, len(n_) if n_ else 1)
    out = []
    for k in range(total):
        tv = t[k % len(t)]
        if tv is NA:
            out.append(NA)
        elif tv is True or (isinstance(tv, (int, float)) and not isinstance(tv, bool) and tv != 0):
            out.append(y[k % len(y)] if y else NA)
        else:
            out.append(n_[k % len(n_)] if n_ else NA)
    return Vector(out)


def isin(x, table) -> Vector:
    """R's ``%in%``: element membership of x in table, vectorised over x."""
    tab = _values(table)

    def contains(v) -> bool:
        for t in tab:
            if v is NA and t is NA:
                return True
            if v is NA or t is NA:
                continue
            if isinstance(v, bool) != isinstance(t, bool):
                # R: TRUE != 1 for %in% purposes across types
                if isinstance(v, bool) or isinstance(t, bool):
                    continue
            if isinstance(v, str) != isinstance(t, str):
                continue
            if v == t:
                return True
        return False

    if isinstance(x, Vector) or isinstance(x, (list, tuple)):
        return Vector([contains(v) for v in _values(x)])
    return Vector([contains(x)])


def pipe(x, f, *args, **keywords):
    """The target of ``%>`` pipes: ``PyRlang.pipe(a, f, b) == f(a, b)``."""
    return f(x, *args, **keywords)


def not_(x):
    """R's ``!``: logical negation, vectorised over Vectors."""
    if isinstance(x, Vector):
        return ~x
    return _r_lnot(x)


def _echo(value) -> None:
    """Internal autoprint helper: echo a value like the R console does."""
    if value is None:
        return
    if isinstance(value, (Vector, DataFrame, Formula, Summary, SummaryMulti, Table)):
        print(value)
    elif isinstance(value, bool):
        print(f"[1] {'TRUE' if value else 'FALSE'}")
    elif isinstance(value, int):
        print(f"[1] {value}")
    elif isinstance(value, float):
        print(f"[1] {format_number(value)}")
    elif isinstance(value, str):
        print(f'[1] "{value}"')
    else:
        print(value)


# -- statistics --------------------------------------------------------------------


def mean(x, na_rm: bool = False):
    """Arithmetic mean; NA unless ``na_rm = True`` (R semantics)."""
    if _has_numpy():
        view = _np_view(_values(x))
        if view is not None:
            arr, mask = view
            if arr.size == 0:
                return float("nan")
            if mask is None:
                return float(arr.mean())
            if not na_rm:
                return NA
            clean = arr[~_vec._np.isnan(arr)]
            return float(clean.mean()) if clean.size else float("nan")
    vals = _numeric(x, "mean", na_rm)
    if not vals:
        return float("nan")
    if vals[0] is NA:
        return NA
    acc = 0.0
    for v in vals:
        acc += v
    return acc / len(vals)


def var(x, na_rm: bool = False):
    """Sample variance (n - 1 denominator), NA-aware like R."""
    if _has_numpy():
        view = _np_view(_values(x))
        if view is not None:
            arr, mask = view
            if arr.size == 0:
                return NA
            clean = arr
            if mask is not None:
                if not na_rm:
                    return NA
                clean = arr[~_vec._np.isnan(arr)]
            if clean.size < 2:
                return NA
            return float(clean.var(ddof=1))
    vals = _numeric(x, "var", na_rm)
    if not vals:
        return NA
    if vals[0] is NA or len(vals) < 2:
        return NA
    n = len(vals)
    acc = 0.0
    for v in vals:
        acc += v
    m = acc / n
    sq = 0.0
    for v in vals:
        sq += (v - m) ** 2
    return sq / (n - 1)


def sd(x, na_rm: bool = False):
    """Sample standard deviation, NA-aware like R."""
    v = var(x, na_rm=na_rm)
    if v is NA:
        return NA
    return math.sqrt(v)


def median(x, na_rm: bool = False):
    """Median; NA unless ``na_rm = True``."""
    if _has_numpy():
        view = _np_view(_values(x))
        if view is not None:
            arr, mask = view
            if arr.size == 0:
                return NA
            clean = arr
            if mask is not None:
                if not na_rm:
                    return NA
                clean = arr[~_vec._np.isnan(arr)]
            if clean.size == 0:
                return NA
            return float(_vec._np.median(clean))
    vals = _numeric(x, "median", na_rm)
    if not vals:
        return NA
    if vals[0] is NA:
        return NA
    srt = sorted(vals)
    n = len(srt)
    mid = n // 2
    if n % 2:
        return srt[mid]
    return (srt[mid - 1] + srt[mid]) / 2


def min(*args, na_rm: bool = False):
    """Minimum; empty input gives Inf, NA-aware like R."""
    vals = _flatten_args(args)
    keep = [v for v in vals if not isinstance(v, str)]
    if len(keep) != len(vals):
        raise PyRError("min() requires numeric values")
    if na_rm:
        keep = [v for v in keep if v is not NA]
    elif any(v is NA for v in keep):
        return NA
    if not keep:
        return float("inf")
    if _has_numpy():
        view = _np_view(keep)
        if view is not None:
            return view[0].min().item()
    best = None
    for v in keep:
        vv = int(v) if isinstance(v, bool) else v
        best = vv if best is None or vv < best else best
    return best


def max(*args, na_rm: bool = False):
    """Maximum; empty input gives -Inf, NA-aware like R."""
    vals = _flatten_args(args)
    keep = [v for v in vals if not isinstance(v, str)]
    if len(keep) != len(vals):
        raise PyRError("max() requires numeric values")
    if na_rm:
        keep = [v for v in keep if v is not NA]
    elif any(v is NA for v in keep):
        return NA
    if not keep:
        return float("-inf")
    if _has_numpy():
        view = _np_view(keep)
        if view is not None:
            return view[0].max().item()
    best = None
    for v in keep:
        vv = int(v) if isinstance(v, bool) else v
        best = vv if best is None or vv > best else best
    return best


def sum(*args, na_rm: bool = False):
    """Sum; empty input gives 0, NA-aware like R."""
    vals = _flatten_args(args)
    for v in vals:
        if isinstance(v, str):
            raise PyRError("invalid 'type' (character) of argument to sum()")
    if na_rm:
        vals = [v for v in vals if v is not NA]
    elif any(v is NA for v in vals):
        return NA
    if _has_numpy():
        view = _np_view(vals)
        if view is not None:
            return view[0].sum().item()
    acc = 0
    for v in vals:
        acc += int(v) if isinstance(v, bool) else v
    return acc


def prod(*args, na_rm: bool = False):
    """Product; empty input gives 1, NA-aware like R."""
    vals = _flatten_args(args)
    for v in vals:
        if isinstance(v, str):
            raise PyRError("invalid 'type' (character) of argument to prod()")
    if na_rm:
        vals = [v for v in vals if v is not NA]
    elif any(v is NA for v in vals):
        return NA
    if _has_numpy():
        view = _np_view(vals)
        if view is not None:
            return view[0].prod().item()
    acc = 1
    for v in vals:
        acc *= int(v) if isinstance(v, bool) else v
    return acc


def _math1(x, fn, name, overflow="nan", np_fn=None):
    def one(v):
        if v is NA:
            return NA
        if isinstance(v, str):
            raise PyRError(f"{name}() requires numeric values")
        try:
            return fn(v)
        except OverflowError:
            return float(overflow)
        except ValueError:
            return float("nan")

    if isinstance(x, Vector):
        if _has_numpy():
            view = _np_view(x.data)
            if view is not None:
                if np_fn is None:
                    np_fn = {
                        "sqrt": _vec._np.sqrt,
                        "exp": _vec._np.exp,
                        "log": _vec._np.log,
                        "log10": _vec._np.log10,
                        "log2": _vec._np.log2,
                    }.get(name)
                if np_fn is not None:
                    with _vec._np.errstate(all="ignore"):
                        return _np_bridge(np_fn(view[0]), view[1])
        return Vector([one(v) for v in x.data])
    vals = _values(x)
    if len(vals) == 1 and is_scalar(x):
        return one(x)
    return Vector([one(v) for v in vals])


def sqrt(x):
    """Square root; negative input gives NaN like R."""
    return _math1(x, math.sqrt, "sqrt")


def exp(x):
    """Exponential (OverflowError -> Inf, like R)."""
    return _math1(x, math.exp, "exp", overflow="inf")


def log(x, base=None):
    """Natural log by default; R's ``log(x, base)`` otherwise."""
    if base is None:
        return _math1(x, math.log, "log", np_fn=_vec._np.log if _has_numpy() else None)
    if _has_numpy():

        def np_fn(arr):
            return _vec._np.log(arr) / _vec._np.log(base)

        return _math1(x, lambda v: math.log(v) / math.log(base), "log", np_fn=np_fn)
    return _math1(x, lambda v: math.log(v) / math.log(base), "log")


def log10(x):
    return _math1(x, math.log10, "log10")


def log2(x):
    return _math1(x, math.log2, "log2")


# -- summary ------------------------------------------------------------------


_SUMMARY_LABELS = ("Min.", "1st Qu.", "Median", "Mean", "3rd Qu.", "Max.")


def _summary_pairs(x):
    vals = _numeric(x, "summary", na_rm=True)
    if not vals:
        return [(lab, NA) for lab in _SUMMARY_LABELS]
    srt = sorted(vals)
    n = len(srt)
    acc = 0.0
    for v in vals:
        acc += v
    return [
        ("Min.", srt[0]),
        ("1st Qu.", _quantile7(srt, 0.25)),
        ("Median", _quantile7(srt, 0.5)),
        ("Mean", acc / n),
        ("3rd Qu.", _quantile7(srt, 0.75)),
        ("Max.", srt[-1]),
    ]


def _sumfmt(v) -> str:
    if v is NA:
        return "NA"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v == int(v) and abs(v) < 1e15:
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    return f"{v:.4g}"


def _pairs_repr(pairs) -> str:
    labels = " ".join(f"{lab:>8}" for lab, _ in pairs)
    values = " ".join(_sumfmt(v).rjust(8) for _, v in pairs)
    return labels + "\n" + values


class Summary:
    """The six-number summary of a numeric vector, printed R-style."""

    def __init__(self, pairs):
        self.pairs = pairs

    def __repr__(self) -> str:
        return _pairs_repr(self.pairs)

    def __str__(self) -> str:
        return self.__repr__()


class SummaryMulti:
    """Per-column summaries of a data frame, printed R-style."""

    def __init__(self, columns):
        self.columns = columns

    def __repr__(self) -> str:
        blocks = []
        for name, pairs in self.columns:
            blocks.append(f"{name} \n{_pairs_repr(pairs)}")
        return "\n\n".join(blocks) + "\n"

    def __str__(self) -> str:
        return self.__repr__()


def summary(x):
    """Six-number summary of a vector, or per-column summary of a data frame."""
    if isinstance(x, DataFrame):
        return SummaryMulti([(name, _summary_pairs(vec)) for name, vec in x._cols.items()])
    return Summary(_summary_pairs(x))


# -- strings ---------------------------------------------------------------------


def _as_str(v) -> str:
    if v is NA:
        return "NA"
    if isinstance(v, str):
        return v
    return fmt_value(v)


def paste(*args, sep=" ", collapse=None):
    """Concatenate with a separator, vectorised over Vector arguments."""
    if not isinstance(sep, str):
        raise PyRError("paste(): 'sep' must be a character string")
    if collapse is not None and not isinstance(collapse, str):
        raise PyRError("paste(): 'collapse' must be a string")
    parts = [_values(a) for a in args]
    parts = [p for p in parts if p]
    if not parts:
        return "" if collapse is None else ""
    total = _py_max(len(p) for p in parts)
    rows = [sep.join(_as_str(p[k % len(p)]) for p in parts) for k in range(total)]
    if collapse is not None:
        return collapse.join(rows)
    if total == 1:
        return rows[0]
    return Vector(rows)


def paste0(*args, collapse=None):
    """Concatenate with no separator, vectorised (like R's ``paste0``)."""
    return paste(*args, sep="", collapse=collapse)


def nchar(x) -> Vector:
    """Number of characters of each string element."""
    if isinstance(x, str):
        return len(x)
    vals = _values(x)
    return Vector([len(v) if isinstance(v, str) else NA for v in vals])


def toupper(x) -> Vector:
    if isinstance(x, str):
        return x.upper()
    return Vector([v.upper() if isinstance(v, str) else NA for v in _values(x)])


def tolower(x) -> Vector:
    if isinstance(x, str):
        return x.lower()
    return Vector([v.lower() if isinstance(v, str) else NA for v in _values(x)])


def substr(x, start, stop) -> Vector:
    """1-based, stop-inclusive substring (R semantics), vectorised over x."""
    start = int(start)
    stop = int(stop)

    def one(v):
        if v is NA:
            return NA
        if not isinstance(v, str):
            raise PyRError("substr() requires character values")
        return v[_py_max(start - 1, 0) : stop]

    if isinstance(x, str):
        return one(x)
    return Vector([one(v) for v in _values(x)])


def substring(x, start, stop=None) -> Vector:
    """Like ``substr`` but with the stop position defaulting to the end."""
    end = 10**9 if stop is None else int(stop)
    return substr(x, start, end)


def sprintf(fmt, *args):
    """Printf-style formatting; vectorised over Vector arguments."""
    if any(isinstance(a, Vector) for a in args):
        cols = [_values(a) for a in args]
        total = _py_max(len(col) for col in cols)
        return Vector(
            [_apply_sprintf(fmt, [col[k % len(col)] for col in cols]) for k in range(total)]
        )
    return _apply_sprintf(fmt, list(args))


def _apply_sprintf(fmt, values):
    if not isinstance(fmt, str):
        raise PyRError("sprintf(): format must be a string")
    try:
        return fmt % tuple(_sprintable(v) for v in values)
    except (TypeError, ValueError) as exc:
        raise PyRError(f"sprintf(): {exc}") from None


def _sprintable(v):
    if v is NA:
        raise PyRError("sprintf(): NA values are not supported")
    return v


def cat(*args, sep=" ", end="") -> None:
    """Print without quoting strings and without a trailing newline (like R)."""
    if not isinstance(sep, str):
        raise PyRError("cat(): 'sep' must be a character string")
    tokens = []
    for a in args:
        if a is None:
            continue
        if isinstance(a, Vector):
            tokens.extend(_as_str(v) for v in a.data)
        elif isinstance(a, (list, tuple)):
            tokens.extend(_as_str(v) for v in _values(a))
        else:
            tokens.append(_as_str(a))
    sys.stdout.write(sep.join(tokens) + end)


# -- data frame helpers -------------------------------------------------------------


def data_frame(**columns) -> DataFrame:
    """``data.frame(name = c(...), ...)`` with scalar recycling like R."""
    if not columns:
        return DataFrame({})
    processed = {k: _values(v) for k, v in columns.items()}
    n = _py_max(len(v) for v in processed.values())
    cols = {}
    for k, v in processed.items():
        if len(v) == n:
            cols[k] = Vector(v)
        elif len(v) == 1:
            cols[k] = Vector(v * n)
        else:
            raise PyRError(f"arguments imply differing number of rows: {len(v)} and {n}")
    return DataFrame(cols)


def nrow(df) -> int:
    """Number of rows of a data frame."""
    if not isinstance(df, DataFrame):
        raise PyRError("nrow() expects a DataFrame")
    return df.nrow()


def ncol(df) -> int:
    """Number of columns of a data frame."""
    if not isinstance(df, DataFrame):
        raise PyRError("ncol() expects a DataFrame")
    return df.ncol()


def names(x) -> Vector:
    """Column names of a data frame as a Vector."""
    if not isinstance(x, DataFrame):
        raise PyRError("names() expects a DataFrame (vectors have no names in PyRlang 0.1)")
    return Vector(list(x.colnames))


class Table(dict):
    """R's ``table()`` result: value counts with the R-style two-line print."""

    def __repr__(self) -> str:
        if not self:
            return "< table of extent 0 >"
        keys = [fmt_value(k, quote_strings=False) for k in self]
        counts = [str(v) for v in self.values()]
        widths = [_py_max(len(k), len(c)) + 1 for k, c in zip(keys, counts, strict=False)]
        return (
            " ".join(k.rjust(w) for k, w in zip(keys, widths, strict=False))
            + "\n"
            + " ".join(c.rjust(w) for c, w in zip(counts, widths, strict=False))
        )

    def __str__(self) -> str:
        return self.__repr__()


def table(x) -> Table:
    """Count occurrences, dropping NA, sorted like R's ``table()``."""
    counts: dict = {}
    for v in _values(x):
        if v is NA:
            continue
        counts[v] = counts.get(v, 0) + 1
    out = Table()
    for k in sorted(counts, key=lambda k: (isinstance(k, str), k)):
        out[k] = counts[k]
    return out


def q(save: str = "default", status: int = 0, run_last: bool = False):
    """Quit the script or the PyRlang REPL, R-style (``q()`` / ``q(status=1)``)."""
    del save, run_last
    raise SystemExit(int(status) if isinstance(status, int) else 0)


def source(path):
    """Run a .pyr file in the caller's global namespace (like R's source())."""
    import inspect

    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise PyRError(f"source(): cannot open {path}: {exc.strerror or exc}") from None
    from PyRlang.transform import PRELUDE, transform

    code = PRELUDE + transform(text, autoprint=True)
    try:
        compiled = compile(code, str(path), "exec")
    except SyntaxError as exc:
        raise PyRError(f"source(): {exc.msg} (line {exc.lineno})") from None
    exec(compiled, inspect.currentframe().f_back.f_globals)
