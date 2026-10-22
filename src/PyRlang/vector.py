"""R-style one-based vectors with NA handling and R-style printing.

This is the heart of PyRlang: :class:`Vector` reproduces R's most visible
semantics — one-based indexing, recycling in arithmetic, element-wise
comparisons, three-way ``NA`` behaviour and ``[1] ...`` console printing.
"""

from __future__ import annotations

import math
import operator as _op
import os

try:
    import numpy as _np
except ImportError:  # numpy is optional; the pure-Python path is always available
    _np = None
if os.environ.get("PYRLANG_NO_NUMPY"):
    _np = None

__all__ = ["NA", "NAType", "PyRError", "Vector", "fmt_value", "format_number", "is_scalar"]


class PyRError(Exception):
    """Runtime error carrying an R-style message."""


class NAType:
    """R's missing-value sentinel, exposed as the singleton :data:`NA`."""

    _instance: NAType | None = None

    def __new__(cls) -> NAType:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "NA"

    def __str__(self) -> str:
        return "NA"

    def __bool__(self) -> bool:
        raise PyRError("missing value where TRUE/FALSE needed")

    def __reduce__(self):  # keep NA a singleton across pickling
        return (_make_na, ())


def _make_na() -> NAType:
    return NA


NA = NAType()

_SCALARS = (bool, int, float)


def is_scalar(value) -> bool:
    """True for R-scalar values: NA, bool, int, float or str."""
    return value is NA or isinstance(value, _SCALARS + (str,))


def format_number(value: float) -> str:
    """Format a float approximately the way R's console does."""
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Inf" if value > 0 else "-Inf"
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return format(value, ".7g")


def fmt_value(value, quote_strings: bool = True) -> str:
    """Format one scalar element in R console style."""
    if value is NA:
        return "NA"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return format_number(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return f'"{value}"' if quote_strings else value
    return repr(value)


# --- element-wise arithmetic ------------------------------------------------


def _r_add(a, b):
    return a + b


def _r_sub(a, b):
    return a - b


def _r_mul(a, b):
    return a * b


def _r_div(a, b):
    # R: 1/0 == Inf, -1/0 == -Inf, 0/0 == NaN
    if b == 0:
        if a == 0:
            return float("nan")
        sign = 1.0 if (a > 0) == (b >= 0) else -1.0
        return sign * float("inf")
    return a / b


def _r_fdiv(a, b):
    # R's %/% is floor division; division by zero gives NaN
    if b == 0:
        return float("nan")
    return a // b


def _r_mod(a, b):
    # R's %% with zero divisor gives NaN; otherwise floor mod (same as Python)
    if b == 0:
        return float("nan")
    return a % b


def _r_pow(a, b):
    try:
        value = a**b
    except ZeroDivisionError:
        return float("inf")  # 0 ** -1
    if isinstance(value, complex):
        return float("nan")  # R: (-8) ** 0.5 -> NaN
    return value


def _r_lnot(v):
    """R's logical negation ``!``, element-wise."""
    if isinstance(v, bool):
        return not v
    if isinstance(v, float):
        if math.isnan(v):
            return NA
        return v == 0
    if isinstance(v, int):
        return v == 0
    raise PyRError("invalid argument type for logical negation")


_ARITH = {
    "+": _r_add,
    "-": _r_sub,
    "*": _r_mul,
    "/": _r_div,
    "//": _r_fdiv,
    "%": _r_mod,
    "**": _r_pow,
}

_CMP = {
    "<": _op.lt,
    "<=": _op.le,
    ">": _op.gt,
    ">=": _op.ge,
    "==": _op.eq,
    "!=": _op.ne,
}

# NumPy fast paths -------------------------------------------------------------
# Values stay plain Python inside Vector; heavy element ops/statistics are
# computed through NumPy when the contents are numeric and NumPy is available.
# NA positions are bridged through the mask so both backends agree bit-for-bit.
_NP_OPS = {}
if _np is not None:
    _NP_OPS = {
        "+": _np.add,
        "-": _np.subtract,
        "*": _np.multiply,
        "/": _np.true_divide,
        "//": _np.floor_divide,
        "%": _np.mod,
        "**": _np.power,
        "<": _np.less,
        "<=": _np.less_equal,
        ">": _np.greater,
        ">=": _np.greater_equal,
        "==": _np.equal,
        "!=": _np.not_equal,
    }

_MAX_INT64 = 2**63 - 1


def _np_unary(values, np_fn):
    """Apply a NumPy unary op when values are numeric; None = fall back."""
    if _np is None or np_fn is None:
        return None
    view = _np_view(values)
    if view is None:
        return None
    arr, mask = view
    if arr.dtype == _np.bool_:
        arr = arr.astype(_np.int64)
    with _np.errstate(all="ignore"):
        r = np_fn(arr)
    return _np_bridge(r, mask)


def _np_view(values):
    """(array, na_mask) view of R values, or None when not representable.

    First tries the C-level conversion (clean numeric lists: no NA, no str):
    ``np.array(values)`` either succeeds with a numeric dtype or yields
    dtype object/str/bool-overflow — anything numeric-unfit falls through to
    ``_np_view_slow`` which scans element-wise and builds an NA mask.
    """
    if _np is None or not values:
        return None
    try:
        arr = _np.array(values)
    except (TypeError, ValueError, OverflowError):
        arr = None
    if arr is not None:
        if arr.dtype.kind in ("i", "f", "b"):
            if arr.dtype.kind == "b":
                arr = arr  # callers cast for arithmetic when needed
            return arr, None
    return _np_view_slow(values)


def _np_view_slow(values):
    """Element-wise conversion: NA → nan (float64) with a position mask."""
    converted = []
    na_positions = []
    saw_float = False
    for pos, v in enumerate(values):
        if v is NA:
            na_positions.append(pos)
            converted.append(_np.nan)
            saw_float = True
        elif isinstance(v, bool):
            converted.append(1 if v else 0)
        elif isinstance(v, int):
            if v > _MAX_INT64 or v < -(2**63):
                return None
            converted.append(v)
        elif isinstance(v, float):
            saw_float = True
            converted.append(v)
        else:
            return None
    if na_positions:
        mask = _np.zeros(len(values), dtype=bool)
        mask[na_positions] = True
    else:
        mask = None
    try:
        dtype = _np.float64 if (saw_float or na_positions) else _np.int64
        arr = _np.array(converted, dtype=dtype)
    except (OverflowError, ValueError, TypeError):
        return None
    return arr, mask


def _np_bridge(arr, mask) -> Vector:
    """Convert a computed NumPy array back, restoring NA from the mask."""
    lst = arr.tolist()
    if mask is not None and mask.any():
        for pos in mask.nonzero()[0].tolist():
            lst[pos] = NA
    return Vector(lst)


def _np_apply2(a, b, name, reverse: bool):
    """NumPy computation for one binary op, or None to fall back."""
    if _np is None or name not in _NP_OPS:
        return None
    va = _np_view(a)
    vb = _np_view(b)
    if va is None or vb is None:
        return None
    arr_a, mask_a = va
    arr_b, mask_b = vb
    if reverse:
        arr_a, arr_b = arr_b, arr_a
        mask_a, mask_b = mask_b, mask_a
    if name not in _CMP:  # arithmetic ops: lift booleans to int (R: TRUE+TRUE=2)
        if arr_a.dtype == _np.bool_:
            arr_a = arr_a.astype(_np.int64)
        if arr_b.dtype == _np.bool_:
            arr_b = arr_b.astype(_np.int64)
    n_a = arr_a.shape[0]
    n_b = arr_b.shape[0]
    if n_a != n_b:
        # R recycling: the shorter operand repeats to the longer length
        longest = max(n_a, n_b)
        try:
            if n_a == 1 or n_b == 1:
                pass  # NumPy broadcasts size-1 operands itself
            else:
                if n_a < longest or n_b < longest:
                    mask_a = _np.resize(mask_a, longest) if mask_a is not None else None
                    mask_b = _np.resize(mask_b, longest) if mask_b is not None else None
                    if n_a < longest:
                        arr_a = _np.resize(arr_a, longest)
                    if n_b < longest:
                        arr_b = _np.resize(arr_b, longest)
        except ValueError:
            return None  # non-multiple lengths: fall back for the R-style warning case
    with _np.errstate(all="ignore"):
        if name == "**" and arr_b.dtype == _np.int64 and (arr_b < 0).any():
            arr_a = arr_a.astype(_np.float64)
        elif name in ("//", "%"):
            zero = arr_b == 0
            safe_b = _np.where(zero, _np.ones_like(arr_b), arr_b)
            r = _NP_OPS[name](arr_a, safe_b)
            if zero.any():
                r = _np.where(zero, _np.nan, r)
            return _np_bridge(r, mask_a if mask_a is not None else mask_b)
        r = _NP_OPS[name](arr_a, arr_b)
    if mask_a is not None and mask_b is not None:
        return _np_bridge(r, mask_a | mask_b)
    return _np_bridge(r, mask_a if mask_a is not None else mask_b)


def _apply2(a, b, fn):
    """Apply ``fn`` to one element pair with R's NA propagation."""
    if a is NA or b is NA:
        return NA
    try:
        return fn(a, b)
    except TypeError as exc:
        raise PyRError(str(exc)) from None


def _truthy(v):
    """R-style truth value; returns None where R would give NA."""
    if v is NA:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        if math.isnan(v):
            return None
        return v != 0
    if isinstance(v, (int,)):
        return v != 0
    raise PyRError("invalid argument type for a logical operation")


class Vector:
    """A 1-based R-style vector.

    ``v[1]`` is the first element, ``v[2:4]`` covers elements 2..4
    (inclusive, R-style), arithmetic recycles shorter operands, and
    ``NA`` propagates the way it does in R.
    """

    __slots__ = ("data",)

    def __init__(self, data=()):
        self.data = list(data)

    # -- display ------------------------------------------------------------

    def __repr__(self) -> str:
        if not self.data:
            return "c()"
        tokens = [fmt_value(v) for v in self.data]
        width = 58  # approx. R's console width used for wrapping
        lines: list[str] = []
        current: list[str] = []
        used = 0
        first_index = 0
        for k, token in enumerate(tokens):
            extra = len(token) + (1 if current else 0)
            if current and used + extra > width:
                lines.append(f"[{first_index + 1}] " + " ".join(current))
                current = [token]
                used = len(token)
                first_index = k
            else:
                current.append(token)
                used += extra
        lines.append(f"[{first_index + 1}] " + " ".join(current))
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.__repr__()

    # -- container protocol ---------------------------------------------------

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __contains__(self, item) -> bool:
        return item in self.data

    def __bool__(self) -> bool:
        n = len(self.data)
        if n == 1:
            if self.data[0] is NA:
                raise PyRError("missing value where TRUE/FALSE needed")
            return bool(self.data[0])
        if n == 0:
            raise PyRError("argument is of length zero")
        raise PyRError("the condition has length > 1")

    def __eq__(self, other):
        return self._elementwise(other, "==")

    def __ne__(self, other):
        return self._elementwise(other, "!=")

    __hash__ = None  # element-wise == makes vectors unhashable, like R semantics hint

    def __lt__(self, other):
        return self._elementwise(other, "<")

    def __le__(self, other):
        return self._elementwise(other, "<=")

    def __gt__(self, other):
        return self._elementwise(other, ">")

    def __ge__(self, other):
        return self._elementwise(other, ">=")

    # -- indexing ------------------------------------------------------------

    def __getitem__(self, key):
        if isinstance(key, bool):
            key = int(key)
        if isinstance(key, int):
            n = len(self.data)
            if key == 0:
                raise PyRError("R vectors are 1-based; index 0 is invalid")
            if key > 0:
                if key > n:
                    raise IndexError(f"subscript out of bounds: length {n}, index {key}")
                return self.data[key - 1]
            drop = -key
            if drop > n:
                return Vector(list(self.data))
            return Vector(self.data[: drop - 1] + self.data[drop:])
        if isinstance(key, slice):
            n = len(self.data)
            start = 1 if key.start is None else key.start
            stop = n if key.stop is None else key.stop
            step = 1 if key.step is None else key.step
            if not all(isinstance(x, int) for x in (start, stop, step)):
                raise PyRError("R-style slices need integer bounds")
            if step <= 0:
                raise PyRError("R-style slicing does not support non-positive steps")
            if start < 1 or stop < 1:
                raise PyRError("R indices start at 1; use negative integers to drop elements")
            # R slices are inclusive on the right: v[2:4] -> elements 2, 3, 4
            return Vector([self.data[k] if k < n else NA for k in range(start - 1, stop, step)])
        if isinstance(key, (Vector, list, tuple)):
            vals = key.data if isinstance(key, Vector) else list(key)
            n = len(self.data)
            if not vals:
                return Vector([])
            if all(v is NA for v in vals):
                return Vector([NA] * len(vals))
            if all(isinstance(v, bool) for v in vals):
                if len(vals) > n:
                    raise PyRError("logical subscript is longer than the vector")
                out = []
                for k in range(n):
                    mask = vals[k % len(vals)]
                    if mask is True:
                        out.append(self.data[k])
                    elif mask is False:
                        continue
                    else:
                        out.append(NA)
                return Vector(out)
            if all(isinstance(v, int) for v in vals):
                positives = any(v > 0 for v in vals)
                negatives = any(v < 0 for v in vals)
                if positives and negatives:
                    raise PyRError("cannot mix positive and negative subscripts")
                if positives:
                    return Vector([self.data[v - 1] if 0 < v <= n else NA for v in vals])
                drops = {-v - 1 for v in vals if v < 0 and -v <= n}
                return Vector([self.data[k] for k in range(n) if k not in drops])
            raise PyRError("invalid subscript vector: mixed element types")
        raise TypeError(f"invalid subscript: {type(key).__name__}")

    def __setitem__(self, key, value):
        if isinstance(key, bool):
            key = int(key)
        if isinstance(key, int):
            n = len(self.data)
            if key <= 0:
                raise PyRError("R vectors are 1-based; indices must be positive")
            if key > n:
                self.data.extend([NA] * (key - n))
            self.data[key - 1] = value
            return
        if isinstance(key, slice):
            start = 1 if key.start is None else key.start
            stop = len(self.data) if key.stop is None else key.stop
            step = 1 if key.step is None else key.step
            positions = list(range(start - 1, stop, step))
            values = list(value)
            if len(values) != len(positions):
                raise PyRError(
                    f"number of items to replace ({len(positions)}) is not of length {len(values)}"
                )
            need = max(positions) + 1 if positions else 0
            if need > len(self.data):
                self.data.extend([NA] * (need - len(self.data)))
            for idx, val in zip(positions, values, strict=True):
                self.data[idx] = val
            return
        if isinstance(key, (Vector, list, tuple)):
            positions = key.data if isinstance(key, Vector) else list(key)
            values = list(value)
            if len(values) != len(positions):
                raise PyRError(
                    f"number of items to replace ({len(positions)}) is not of length {len(values)}"
                )
            for pos, val in zip(positions, values, strict=True):
                self[int(pos)] = val
            return
        raise TypeError(f"invalid subscript: {type(key).__name__}")

    # -- arithmetic ----------------------------------------------------------

    def _operand_values(self, other):
        if isinstance(other, Vector):
            return other.data
        if isinstance(other, (list, tuple)):
            return list(other)
        if is_scalar(other):
            return [other]
        return None

    def _elementwise(self, other, name, reverse: bool = False):
        vals = self._operand_values(other)
        if vals is None:
            return NotImplemented
        n = len(self.data)
        m = len(vals)
        if n == 0 or m == 0:
            return Vector([])
        np_result = _np_apply2(self.data, vals, name, reverse)
        if np_result is not None:
            return np_result
        fn = _ARITH.get(name) or _CMP[name]
        out = []
        for k in range(max(n, m)):
            a = self.data[k % n]
            b = vals[k % m]
            out.append(_apply2(b, a, fn) if reverse else _apply2(a, b, fn))
        return Vector(out)

    def __add__(self, other):
        return self._elementwise(other, "+")

    def __radd__(self, other):
        return self._elementwise(other, "+")

    def __sub__(self, other):
        return self._elementwise(other, "-")

    def __rsub__(self, other):
        return self._elementwise(other, "-", reverse=True)

    def __mul__(self, other):
        return self._elementwise(other, "*")

    def __rmul__(self, other):
        return self._elementwise(other, "*")

    def __truediv__(self, other):
        return self._elementwise(other, "/")

    def __rtruediv__(self, other):
        return self._elementwise(other, "/", reverse=True)

    def __floordiv__(self, other):
        return self._elementwise(other, "//")

    def __rfloordiv__(self, other):
        return self._elementwise(other, "//", reverse=True)

    def __mod__(self, other):
        return self._elementwise(other, "%")

    def __rmod__(self, other):
        return self._elementwise(other, "%", reverse=True)

    def __pow__(self, other):
        return self._elementwise(other, "**")

    def __rpow__(self, other):
        return self._elementwise(other, "**", reverse=True)

    # -- unary ---------------------------------------------------------------

    def _unary(self, fn):
        out = []
        for v in self.data:
            if v is NA:
                out.append(NA)
            else:
                try:
                    out.append(fn(v))
                except TypeError as exc:
                    raise PyRError(str(exc)) from None
        return Vector(out)

    def __neg__(self):
        r = _np_unary(self.data, _np.negative if _np is not None else None)
        if r is not None:
            return r
        return self._unary(lambda v: -v)

    def __pos__(self):
        r = _np_unary(self.data, (lambda a: a) if _np is not None else None)
        if r is not None:
            return r
        return self._unary(lambda v: +v)

    def __abs__(self):
        r = _np_unary(self.data, _np.abs if _np is not None else None)
        if r is not None:
            return r
        return self._unary(abs)

    def __invert__(self):
        # Python-side convenience: ~v is R's logical negation, element-wise
        if _np is not None:
            view = _np_view(self.data)
            if view is not None:
                arr, mask = view
                r = arr == 0
                lst = r.tolist()
                if mask is not None and mask.any():
                    for pos in mask.nonzero()[0].tolist():
                        lst[pos] = NA
                return Vector(lst)
        return self._unary(_r_lnot)

    # -- logic ---------------------------------------------------------------

    def _logic(self, other, combine):
        """``combine`` is the string 'and' or 'or' (R vectorised logic)."""
        vals = self._operand_values(other)
        if vals is None:
            return NotImplemented
        n = len(self.data)
        m = len(vals)
        if n == 0 or m == 0:
            return Vector([])
        if _np is not None:
            va = _np_view(self.data)
            vb = _np_view(vals)
            if va is not None and vb is not None:
                arr, mask_a = va
                other_arr, mask_b = vb
                valid = _np.ones(arr.shape, dtype=bool)
                if arr.dtype == _np.float64:
                    valid &= ~_np.isnan(arr)
                valid_b = _np.ones(other_arr.shape, dtype=bool)
                if other_arr.dtype == _np.float64:
                    valid_b &= ~_np.isnan(other_arr)
                ta = arr != 0
                tb = other_arr != 0
                fn = _np.logical_and if combine == "and" else _np.logical_or
                both = fn(_np.where(valid, ta, True), _np.where(valid_b, tb, True))
                r = _np.where(valid & valid_b, both.astype(float), _np.nan)
                mask = None
                for mk in (mask_a, mask_b):
                    if mk is not None:
                        mask = mk if mask is None else (mask | mk)
                lst = r.tolist()
                if mask is not None and mask.any():
                    mlist = mask.tolist()
                    return Vector(
                        [
                            NA if m else (NA if v != v else bool(v))
                            for m, v in zip(mlist, lst, strict=True)
                        ]
                    )
                return Vector([NA if v != v else bool(v) for v in lst])
        out = []
        for k in range(max(n, m)):
            ta = _truthy(self.data[k % n])
            tb = _truthy(vals[k % m])
            if ta is None or tb is None:
                out.append(NA)
            else:
                out.append((ta and tb) if combine == "and" else (ta or tb))
        return Vector(out)

    def __and__(self, other):
        return self._logic(other, "and")

    def __rand__(self, other):
        return self._logic(other, "and")

    def __or__(self, other):
        return self._logic(other, "or")

    def __ror__(self, other):
        return self._logic(other, "or")
