# PyRlang

**R-style syntax, running on pure Python.** No R runtime, no compilation, zero dependencies.

PyRlang lets you write R the way R programmers actually type it — `x <- c(1, 2)`, `1:10`, `df$col`,
`%>%`, `%in%`, `y ~ x` — and runs it as ordinary Python underneath. It also ships the R-flavoured
data types as a normal Python library, usable from plain `.py` files.

- **PyPI distribution name:** `pyr4py`
  (PyPI compares names with `-`/`_` stripped, so the whole family is blocked: `pyr` is a 2013
  REPL, `pyrlang` is an actively developed BEAM runtime, and therefore `pyr-lang`/`PyRlang`
  are rejected on upload too. `pyr4py` — "PyR for Python" — is the distribution name)
- **Import name:** `PyRlang` (`import PyRlang`, `from PyRlang import *`)
- **License:** GPL-3.0-or-later
- **Python:** >= 3.10

## Install

```bash
pip install pyr4py            # zero-dependency core
pip install "pyr4py[all]"     # + NumPy fast path, matplotlib graphics, pandas interop
pip install "pyr4py[accel]"   # + NumPy only
```

**Speed:** when NumPy is installed the element-wise operations and statistics run
vectorised automatically (about 1.2–6× on real workloads; `PYRLANG_NO_NUMPY=1`
forces the pure-Python path). Set `PYRLANG_NO_NUMPY=1` to compare.

## Two ways to use it

### 1. R-style scripts (`.pyr`) — full syntax

Write `hello.pyr`:

```r
x <- c(2, 4.5, 8, 1, 3.3, NA)
mean(x, na.rm = TRUE)
summary(x)

v <- 1:5
v[1]              # one-based: the FIRST element
v[-1]             # drops the first element, R-style

df <- data.frame(
  name = c("ada", "bob"),
  age  = c(34, 47)
)
df$age
df[df$age > 35, ]
df$senior <- df$age > 40

df$age %>% mean() %>% round(2)
10 %in% c(4, 8, 10)
paste("R", "on", "Python", sep = "-") |> toupper()
f <- wage ~ age
```

Run it like an R script:

```bash
PyRlang hello.pyr          # or: python -m PyRlang hello.pyr
```

Top-level expressions echo their results exactly like the R console,
vectors print as `[1] 2 4.5 8 1 3.3 NA`.

### 2. Interactive REPL

```text
$ PyRlang
PyRlang 0.1.0 on Python 3.12 — R-style syntax, pure Python
Try: x <- c(1, 2, 3); mean(x).  exit() or Ctrl-D to quit.
>> x <- c(1, 2, 3)
>> mean(x)
[1] 2
>> 1:5 %>% sum()
[1] 15
```

### 3. As a Python library

```python
from PyRlang import *

v = c(1, 2, 3)
v[1]  # 1 — one-based
mean(v)  # 2.0
f = Formula("y ~ x")
df = data_frame(age=c(34, 47), wage=c(21.5, 33.0))
summary(df)  # R-style six-number summaries
```

## Syntax supported in transform mode

(`.pyr` files, the REPL, and `PyRlang -e` — plain `.py` files are never touched.)

| R syntax        | becomes                | notes                                                                 |
|-----------------|------------------------|-----------------------------------------------------------------------|
| `x <- e`        | `x = e`                | `<` and `-` must be adjacent, exactly like the real R parser          |
| `x < -e`        | unchanged              | a space keeps it a Python comparison                                  |
| `<<-`           | not supported          | clear error message                                                   |
| `a:b`           | `seq(a, b)`            | outside `[]`/`{}`; not after `lambda`, not annotations, not slices    |
| `x ^ y`         | `x ** y`               |                                                                       |
| `x %% y`        | `x % y`                |                                                                       |
| `a && b`        | `a and b`              | adjacent pair only, like R's scalar operators                         |
| `a \|\| b`      | `a or b`               |                                                                       |
| `!x`            | `PyRlang.not_(x)`          | element-wise negation — works on vectors                              |
| `a %in% b`      | `PyRlang.isin(a, b)`       | vectorised membership                                                 |
| `a %>% f(b)`    | `PyRlang.pipe(a, f, b)`    | magrittr; native R pipe `a \|> f(b)` too                              |
| `y ~ x + z`     | `Formula('y ~ x + z')` | including inside call arguments: `lm(y ~ x, data = d)` style          |
| `df$col`        | `df.col`               |                                                                       |
| `data.frame(…)` | `DataFrame(…)`         | also `read.csv`, `write.csv`, `which.max`, `which.min`, `na.rm=`, `length.out=`, `names.arg=` |

## R block syntax

Braces become indentation, exactly where R uses them:

```r
if (total > 10) {
  msg <- "big"
} else if (total == 10) {
  msg <- "ten"
} else {
  msg <- "small"
}

for (i in 1:5) {
  total <- total + i
}

repeat {
  guard <- guard + 3
  if (guard >= 9) {
    break
  }
}
```

`next` also works. Lines *outside* R braces are left byte-identical, so
plain Python code in `.pyr` files is never reshaped. Not supported:
R's `function(x) {...}` definitions (use Python `def`) and one-line
`if (x) y <- 2` forms.

## R console feel (REPL)

`PyRlang` with no arguments is a terminal in the spirit of R's console,
built like IPython over Python: TAB completes names, history persists at
`~/.pyr_history`, `_` holds the last printed result, `q()` quits,
`source("file.pyr")` runs a script in-session:

```text
>> x <- c(2, 4.5, 8, 1, 3.3, NA)
>> mean(x, na.rm = TRUE)
[1] 3.76
>> _
[1] 3.76
```

## Graphics (optional)

With `matplotlib` installed (`pip install "pyr4py[graphics]"`):

```r
plot(x, y, col = "steelblue")      # scatter (type = "l" for a line)
hist(x, breaks = 20)
barplot(heights, names.arg = c("a", "b"))
```

Figures are saved as `plot_01.png`, `hist_01.png`, … and the path is printed,
so both scripts and the REPL stay non-blocking.

## pandas interop (optional)

```python
from PyRlang import data_frame, to_pandas, from_pandas

pdf = to_pandas(data_frame(age=c(34, 47)))  # pandas DataFrame (NA -> NaN)
df = from_pandas(pdf)  # back to PyRlang (NaN -> NA)
```

## Semantics, by design

- **One-based indexing.** `v[1]` is the first element; index 0 is an error with an
  R-style message. `v[2:4]` returns elements 2, 3, 4 (inclusive, like R), and
  out-of-range slices pad with `NA`.
- **Negative subscripts drop elements.** `v[-1]` removes the first element.
  (This differs deliberately from Python's negative indexing.)
- **Recycling.** `c(1, 2) + c(1, 2, 3, 4)` recycles the shorter vector, like R.
- **NA everywhere.** A real `NA` sentinel: `NA + 1` is `NA`, `mean(c(1, NA))` is `NA`
  unless you write `na.rm = TRUE`, `if (NA)` raises R's error message.
- **R-flavoured printing.** Vectors print as `[1] 1 2 3`, strings quoted, logicals as
  `TRUE`/`FALSE`, six-number summaries in R's column layout.
- **Division by zero is `Inf`/`NaN`**, not an exception — like R.

## What ships in the library

- Constructors/inspection: `c`, `seq`, `rep`, `length`, `unique`, `sort`, `rev`,
  `head`, `tail`, `which`, `which.max`, `which.min`, `table`
- Statistics: `mean`, `median`, `sd`, `var`, `min`, `max`, `sum`, `prod`,
  `summary`, `sqrt`, `exp`, `log`, all NA-aware
- Strings: `paste`, `paste0`, `sprintf`, `nchar`, `toupper`, `tolower`,
  `substr`, `substring`, `cat`
- Data: `data.frame`, `$`, R-style row/column subsetting, `nrow`, `ncol`,
  `names`, `read.csv`, `write.csv`
- Logic: `ifelse`, `%in%`, element-wise `&`, `|`, `!`, vectorised comparisons

## Honest limitations (v0.1.2)

- R block syntax has limits: `function(x) {...}` definitions are not translated
  (use Python `def`); one-line `if (x) y <- 2` forms are not supported.
- `->` (right assignment) is not yet transformed.
- `lm`, `glm`, `ggplot` and the modelling stack do not exist yet; `Formula` is
  data only and plotting covers `plot`, `hist`, `barplot`.
- No packages/namespaces; Python modules are imported normally.
- Type annotations in `.pyr` files are not supported (R mode treats `n:m` as a range).
- Only Python >= 3.10 is supported.

## Versioning policy

Releases bump **only the last digit** of the version (`0.1.1` → `0.1.2` → …);
the `0.1` prefix is fixed for this development line.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff format . && ruff check .
python -m build
twine check dist/*
```

Run the examples:

```bash
python -m PyRlang examples/basics.pyr
python -m PyRlang examples/dataframe.pyr
PyRlang
```

## Publishing to PyPI

The PyPI name for this project is **`pyr4py`** (taken-name note above).

```bash
python -m build
twine check dist/*
twine upload dist/pyr4py-0.1.0*
```

Use `--repository testpypi` to rehearse on TestPyPI, or configure an API token:

```ini
# ~/.pypirc
[pypi]
username = __token__
password = pypi-xxxxxxxx
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).