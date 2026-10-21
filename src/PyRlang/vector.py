"""R-style one-based vectors with NA handling and R-style printing.

This is the heart of PyRlang: :class:`Vector` reproduces R's most visible
semantics — one-based indexing, recycling in arithmetic, element-wise
comparisons, three-way ``NA`` behaviour and ``[1] ...`` console printing.
"""

from __future__ import annotations

import math
import operator as _op

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
        return self._unary(lambda v: -v)

    def __pos__(self):
        return self._unary(lambda v: +v)

    def __abs__(self):
        return self._unary(abs)

    def __invert__(self):
        # Python-side convenience: ~v is R's logical negation, element-wise
        return self._unary(_r_lnot)

    # -- logic ---------------------------------------------------------------

    def _logic(self, other, combine):
        vals = self._operand_values(other)
        if vals is None:
            return NotImplemented
        n = len(self.data)
        m = len(vals)
        if n == 0 or m == 0:
            return Vector([])
        out = []
        for k in range(max(n, m)):
            ta = _truthy(self.data[k % n])
            tb = _truthy(vals[k % m])
            if ta is None or tb is None:
                out.append(NA)
            else:
                out.append(combine(ta, tb))
        return Vector(out)

    def __and__(self, other):
        return self._logic(other, lambda a, b: a and b)

    def __rand__(self, other):
        return self._logic(other, lambda a, b: a and b)

    def __or__(self, other):
        return self._logic(other, lambda a, b: a or b)

    def __ror__(self, other):
        return self._logic(other, lambda a, b: a or b)
