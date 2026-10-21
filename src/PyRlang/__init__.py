"""PyRlang — R-style syntax for pure Python.

* In plain Python: ``from PyRlang import *`` gives you one-based Vectors,
  data frames, formulas, pipes and NA-aware statistics.
* In ``.pyr`` files / the REPL / ``PyRlang -e``: plus full R-ish syntax —
  ``x <- c(1, 2)``, ``1:10``, ``%>%``, ``%in%``, ``y ~ x``, ``df$col`` …

PyPI distribution name: ``pyr-lang`` (``PyRlang`` normalises to ``pyrlang``,
which — like ``pyr`` — is already taken on PyPI).
"""

from PyRlang.__version__ import __version__
from PyRlang.dataframe import DataFrame
from PyRlang.formula import Formula
from PyRlang.funcs import (
    Summary,
    SummaryMulti,
    Table,
    c,
    cat,
    data_frame,
    exp,
    head,
    ifelse,
    isin,
    length,
    log,
    log2,
    log10,
    max,
    mean,
    median,
    min,
    names,
    nchar,
    ncol,
    not_,
    nrow,
    paste,
    paste0,
    pipe,
    prod,
    rep,
    rev,
    sd,
    seq,
    sort,
    sprintf,
    sqrt,
    substr,
    substring,
    sum,
    summary,
    table,
    tail,
    tolower,
    toupper,
    unique,
    var,
    which,
    which_max,
    which_min,
)
from PyRlang.funcs import (
    _echo as _echo,  # noqa: F401  # re-exported for PyRlang._echo (used by the transformer)
)
from PyRlang.io import read_csv, write_csv
from PyRlang.vector import NA, NAType, PyRError, Vector

T = True
F = False
TRUE = True
FALSE = False
NULL = None
NaN = float("nan")
Inf = float("inf")

__all__ = [
    "DataFrame",
    "F",
    "Formula",
    "Inf",
    "NA",
    "NAType",
    "NaN",
    "NULL",
    "PyRError",
    "Summary",
    "SummaryMulti",
    "T",
    "Table",
    "TRUE",
    "FALSE",
    "Vector",
    "__version__",
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
    "read_csv",
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
    "write_csv",
]
