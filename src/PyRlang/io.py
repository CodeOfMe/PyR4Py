"""CSV reading/writing with R-ish defaults (header row, ``NA`` for missing)."""

from __future__ import annotations

import csv
import math

from PyRlang.dataframe import DataFrame
from PyRlang.vector import NA, PyRError, Vector, format_number

__all__ = ["read_csv", "write_csv"]


def _clean_na(cell: str) -> str | None:
    if cell in ("", "NA"):
        return None
    return cell


def _is_int(s: str) -> bool:
    body = s[1:] if s and s[0] in "+-" else s
    return body.isdigit() and "_" not in s


def _is_float(s: str) -> bool:
    if _is_int(s):
        return True
    lowered = s.lower().lstrip("+-")
    if lowered in ("nan", "inf", "infinity"):
        return False
    try:
        float(s)
    except ValueError:
        return False
    return True


def _coerce_column(raw: list[str]) -> Vector:
    cleaned = [_clean_na(c) for c in raw]
    non_missing = [c for c in cleaned if c is not None]
    if non_missing and all(_is_int(c) for c in non_missing):
        return Vector([int(c) if c is not None else NA for c in cleaned])
    if non_missing and all(_is_float(c) for c in non_missing):
        return Vector([float(c) if c is not None else NA for c in cleaned])
    return Vector([c if c is not None else NA for c in cleaned])


def read_csv(path, header: bool = True) -> DataFrame:
    """Read a CSV file into a :class:`DataFrame` (numeric types inferred)."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = [row for row in csv.reader(fh) if row]
    if not rows:
        return DataFrame({})
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    if header:
        names = rows[0]
        body = rows[1:]
    else:
        names = [f"V{i + 1}" for i in range(width)]
        body = rows
    columns = {name: _coerce_column([row[k] for row in body]) for k, name in enumerate(names)}
    return DataFrame(columns)


def _csv_value(v) -> str:
    if v is NA:
        return "NA"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        return format_number(v)
    return str(v)


def write_csv(df: DataFrame, path) -> None:
    """Write a :class:`DataFrame` as CSV with R-style ``NA`` / ``TRUE``/``FALSE``."""
    if not isinstance(df, DataFrame):
        raise PyRError("write_csv() expects a DataFrame")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(df.colnames)
        n = df.nrow()
        for r in range(n):
            writer.writerow([_csv_value(vec.data[r]) for vec in df._cols.values()])
