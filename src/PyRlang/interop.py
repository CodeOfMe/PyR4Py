"""Optional pandas interop: ``to_pandas(df)`` and ``from_pandas(pd_frame)``."""

from __future__ import annotations

from PyRlang.dataframe import DataFrame
from PyRlang.vector import NA, PyRError, Vector

__all__ = ["from_pandas", "to_pandas"]


def _pandas():
    try:
        import pandas
    except ImportError:
        raise PyRError("pandas interop needs pandas: pip install pandas") from None
    return pandas


def to_pandas(df):
    """Convert a PyRlang DataFrame to a pandas DataFrame (NA -> NaN)."""
    pd = _pandas()
    if not isinstance(df, DataFrame):
        raise PyRError("to_pandas() expects a DataFrame")
    columns = {}
    for name, col in df._cols.items():
        values = []
        for v in col.data:
            if v is NA:
                values.append(float("nan"))
            elif isinstance(v, bool):
                values.append(bool(v))
            else:
                values.append(v)
        columns[name] = values
    return pd.DataFrame(columns)


def from_pandas(pdf) -> DataFrame:
    """Convert a pandas DataFrame to a PyRlang DataFrame (NaN/None -> NA)."""
    _pandas()
    if isinstance(pdf, DataFrame):
        raise PyRError("from_pandas() expects a pandas DataFrame, not a PyRlang one")
    if not hasattr(pdf, "columns") or not hasattr(pdf, "items"):
        raise PyRError("from_pandas() expects a pandas DataFrame")
    columns = {}
    for name in pdf.columns:
        series = pdf[name]
        values = []
        for v in series.tolist():
            try:
                missing = v is None or (isinstance(v, float) and v != v)
            except TypeError:
                missing = False
            values.append(NA if missing else v)
        columns[str(name)] = Vector(values)
    return DataFrame(columns)
