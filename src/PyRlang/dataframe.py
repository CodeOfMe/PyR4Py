"""R-style data frames: ``data.frame(age = c(1, 2), wage = c(...))``.

Columns are :class:`~PyRlang.vector.Vector` objects; ``df$col`` works through
attribute access, row filtering through R-style comma subscripts::

    df[df$age > 30, ]                 # rows
    df[df$age > 30, c("name", "w")]   # rows and columns
    df["age"]                         # one-column data frame (R semantics)
    df$wage                           # the column, as a Vector
"""

from __future__ import annotations

from PyRlang.vector import PyRError, Vector, fmt_value

__all__ = ["DataFrame"]


def _plain(value) -> str:
    """Element formatting inside a data frame (strings unquoted, R-style)."""
    return fmt_value(value, quote_strings=False)


class DataFrame:
    """A column-oriented table with R access semantics."""

    def __init__(self, columns: dict[str, Vector] | None = None):
        cols: dict[str, Vector] = {}
        lengths: set[int] = set()
        for name, values in (columns or {}).items():
            vec = values if isinstance(values, Vector) else Vector(list(values))
            cols[name] = vec
            lengths.add(len(vec))
        if len(lengths) > 1:
            raise PyRError(
                "arguments imply differing number of rows: "
                + ", ".join(str(x) for x in sorted(lengths))
            )
        object.__setattr__(self, "_cols", cols)

    # -- attribute access --------------------------------------------------

    def __getattr__(self, name):
        # only reached when normal attribute lookup fails
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            cols = object.__getattribute__(self, "_cols")
        except AttributeError:
            raise AttributeError(name) from None
        if name in cols:
            return cols[name]
        available = ", ".join(cols) if cols else "(none)"
        raise AttributeError(f"column '{name}' not found; columns: {available}")

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        cols = object.__getattribute__(self, "_cols")
        n = self.nrow()
        vec = value if isinstance(value, Vector) else Vector([value])
        if len(vec) == 1 and n > 1:
            vec = Vector([vec[1]] * n)
        elif len(vec) != n:
            raise PyRError(f"length mismatch assigning column '{name}': {len(vec)} vs {n}")
        cols[name] = vec

    # -- shape ---------------------------------------------------------------

    def nrow(self) -> int:
        if not self._cols:
            return 0
        return len(next(iter(self._cols.values())).data)

    def ncol(self) -> int:
        return len(self._cols)

    @property
    def colnames(self) -> list[str]:
        return list(self._cols)

    # -- subsetting ------------------------------------------------------------

    def _rows(self, sel) -> DataFrame:
        n = self.nrow()
        if isinstance(sel, bool):
            sel = int(sel)
        if isinstance(sel, slice):
            if sel == slice(None):
                return self._copy()
            raise PyRError("only the full-row slice df[:] is supported")
        if isinstance(sel, int):
            if not (1 <= sel <= n):
                raise IndexError(f"subscript out of bounds: {n} rows, row {sel}")
            return self._take([sel - 1])
        if isinstance(sel, (Vector, list, tuple)):
            vals = sel.data if isinstance(sel, Vector) else list(sel)
            if all(isinstance(v, bool) for v in vals):
                if len(vals) != n:
                    raise PyRError(f"row mask length {len(vals)} does not match {n} rows")
                return self._take([k for k, v in enumerate(vals) if v is True])
            if all(isinstance(v, int) for v in vals):
                if any(v == 0 for v in vals):
                    raise PyRError("R rows are 1-based; row index 0 is invalid")
                return self._take([v - 1 for v in vals])
            raise PyRError("row subscripts must be logical or integer")
        raise PyRError(f"cannot subset rows with {type(sel).__name__}")

    def _cols_sel(self, sel, drop: bool):
        colmap = self._cols
        if isinstance(sel, str):
            if sel not in colmap:
                raise PyRError(f"column '{sel}' not found")
            return colmap[sel] if drop else self._copy({sel: colmap[sel]})
        vals = sel.data if isinstance(sel, Vector) else list(sel)
        names: list[str] = []
        if all(isinstance(v, str) for v in vals) and vals:
            for v in vals:
                if v not in colmap:
                    raise PyRError(f"column '{v}' not found")
                names.append(v)
        elif all(isinstance(v, int) for v in vals) and vals:
            for v in vals:
                if v == 0:
                    raise PyRError("R columns are 1-based; column index 0 is invalid")
                if not (1 <= v <= len(colmap)):
                    raise IndexError(
                        f"subscript out of bounds: {len(colmap)} columns, column {v} requested"
                    )
                names.append(list(colmap)[v - 1])
        else:
            raise PyRError("column subscripts must be names or positive integers")
        sub = {name: colmap[name] for name in names}
        if drop and len(names) == 1:
            return sub[names[0]]
        return self._copy(sub)

    def __getitem__(self, key):
        if isinstance(key, tuple):
            if len(key) == 0:
                raise PyRError("empty subscript")
            if len(key) == 1:
                return self._rows(key[0])
            if len(key) == 2:
                rows_sel, cols_sel = key
                df = self._rows(rows_sel)
                return df._cols_sel(cols_sel, drop=True)
            raise PyRError("data frames take at most two subscripts (rows, cols)")
        if isinstance(key, slice):
            if key == slice(None):
                return self._copy()
            raise PyRError("only the full-row slice df[:] is supported")
        if isinstance(key, str):
            return self._cols_sel(key, drop=False)
        if isinstance(key, int):
            return self._cols_sel(key, drop=False)
        if isinstance(key, Vector):
            vals = key.data
            if vals and all(isinstance(v, str) for v in vals):
                return self._cols_sel(key, drop=False)
            if vals and all(isinstance(v, (int, bool)) for v in vals):
                # R: df[c(1, 3)] selects columns by position
                return self._cols_sel(key, drop=False)
            raise PyRError("cannot use this vector as a column subscript")
        raise PyRError(f"cannot subscript a data frame with {type(key).__name__}")

    def _take(self, indices: list[int]) -> DataFrame:
        n = self.nrow()
        for i in indices:
            if not (0 <= i < n):
                raise IndexError(f"subscript out of bounds: {n} rows, row {i + 1}")
        return DataFrame(
            {name: Vector([vec.data[i] for i in indices]) for name, vec in self._cols.items()}
        )

    def _copy(self, columns=None) -> DataFrame:
        cols = columns if columns is not None else self._cols
        return DataFrame({name: Vector(list(vec.data)) for name, vec in cols.items()})

    def __eq__(self, other):
        return NotImplemented

    __hash__ = None

    # -- printing -----------------------------------------------------------

    def __repr__(self) -> str:
        cols = self._cols
        if not cols:
            return "data frame with 0 columns and 0 rows"
        n = self.nrow()
        headers = list(cols)
        rows_label = str(n)
        label_width = len(rows_label)
        cells = {name: [_plain(v) for v in vec.data] for name, vec in cols.items()}
        widths = {
            name: max(len(name), max((len(c) for c in cells[name]), default=0)) for name in headers
        }
        lines = [" ".join([" " * label_width] + [h.rjust(widths[h]) for h in headers])]
        for r in range(n):
            parts = [str(r + 1).rjust(label_width)]
            parts += [cells[name][r].rjust(widths[name]) for name in headers]
            lines.append(" ".join(parts))
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.__repr__()
