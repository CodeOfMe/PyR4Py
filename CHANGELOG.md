# Changelog

All notable changes to PyRlang are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-10-21

### Changed

- Project home moved to `CodeOfMe/PyR4Py` on GitHub; `pyproject.toml` metadata
  now points at the renamed repository. (Release 0.1.0 on PyPI still shows the
  previous URL, which GitHub redirects automatically.)

### Fixed

- Nothing functional; release re-cut so PyPI metadata carries the new URLs.

## [0.1.0] - 2026-10-21

### Added

- One-based R-style `Vector` with recycling arithmetic, element-wise comparisons,
  negative-subscript exclusion, NA propagation and R-console printing (`[1] ...`).
- `DataFrame` with `df$col` attribute access, R-style row/column subsetting
  (`df[mask, ]`, `df[mask, cols]`, `df[col]`) and scalar-recycling column assignment.
- `Formula("y ~ x")` data object.
- The R function library: `c seq rep length unique sort rev head tail which
  which.max which.min table ifelse %in% pipe paste paste0 sprintf nchar toupper
  tolower substr substring cat sum prod min max mean median sd var summary
  sqrt exp log log10 log2`, all NA-aware.
- `read.csv` / `write.csv` with R-style `NA` and `TRUE`/`FALSE` literals.
- Source transformer for `.pyr` files / REPL / `-e`: `x <- v`, `a:b`, `x ^ y`,
  `x %% y`, `a && b`, `a \|\| b`, `!x`, `a %in% b`, `a %>% f(b)`, `a \|> f(b)`,
  `y ~ x`, `df$col`, `data.frame(...)`, `which.max`, `na.rm=`, `length.out=` —
  with the R parser's adjacency rule for `<-` so `x < -1` stays a comparison.
- Interactive REPL (`PyRlang`) with R-style value echo.
- CLI: `PyRlang script.pyr`, `PyRlang -e CODE`, `PyRlang --version`; top-level results echo
  like the R console.
- Test suite covering vectors, functions, data frames, the transformer and the CLI.

[0.1.1]: https://github.com/CodeOfMe/PyR4Py/releases/tag/v0.1.1

[0.1.0]: https://github.com/CodeOfMe/PyR4Py/releases/tag/v0.1.0