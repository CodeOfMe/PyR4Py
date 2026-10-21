"""End-to-end tests: run the CLI against the bundled examples."""

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run_cli(args, stdin=None):
    return subprocess.run(
        [sys.executable, "-m", "PyRlang", *args],
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_basics_example():
    result = run_cli(["examples/basics.pyr"])
    assert result.returncode == 0, result.stderr
    assert "3.76" in result.stdout  # mean(x, na.rm = TRUE)
    assert "Median" in result.stdout  # summary(x)
    assert "sum(1:100) = 5050" in result.stdout
    assert "R-ON-PYTHON" in result.stdout


def test_dataframe_example():
    result = run_cli(["examples/dataframe.pyr"])
    assert result.returncode == 0, result.stderr
    assert "ada" in result.stdout
    assert "wage ~ age" in result.stdout
    assert "[1] 2" in result.stdout  # which.max(df$age) -> bob
    assert "FALSE" in result.stdout and "TRUE" in result.stdout


def test_eval_flag():
    result = run_cli(["-e", 'x <- 2 ^ 8\ncat(x, "\\n")'])
    assert result.returncode == 0, result.stderr
    assert "256" in result.stdout


def test_version_flag():
    result = run_cli(["--version"])
    assert result.returncode == 0
    assert "pyr-lang" in result.stdout


def test_repl_stdin():
    result = run_cli([], stdin="x <- 1:3\nx\n")
    assert result.returncode == 0, result.stderr
    assert "[1] 1 2 3" in result.stdout


def test_missing_script_is_friendly():
    result = run_cli(["does-not-exist.pyr"])
    assert result.returncode == 2
    assert "cannot open" in result.stderr


@pytest.mark.parametrize(
    "code",
    [
        "x <- c(1, 2)\ny <- x + c(10, 20)\ncat(y, sep=' ')",
        "m <- summary(1:10)\ncat(mean(1:10))",
        "v <- 1:3 %in% c(2)\ncat(v[1])",
    ],
)
def test_eval_snippets(code):
    result = run_cli(["-e", code])
    assert result.returncode == 0, result.stderr
