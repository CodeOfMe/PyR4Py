import math

import pytest

from PyRlang import (
    NA,
    c,
    head,
    ifelse,
    isin,
    length,
    log,
    max,
    mean,
    median,
    min,
    nchar,
    paste,
    paste0,
    pipe,
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
    toupper,
    unique,
    var,
    which,
    which_max,
    which_min,
)


def test_seq_variants():
    assert list(seq(1, 10)) == list(range(1, 11))
    assert list(seq(10)) == list(range(1, 11))
    assert list(seq(5, 1)) == [5, 4, 3, 2, 1]
    assert len(seq(1, 5, by=-1)) == 0
    assert list(seq(0, 1, by=0.25)) == [0, 0.25, 0.5, 0.75, 1.0]
    assert list(seq(1, 10, length_out=4)) == [1, 4, 7, 10]


def test_rep_variants():
    assert list(rep(c(1, 2, 3), times=2)) == [1, 2, 3, 1, 2, 3]
    assert list(rep(c(1, 2, 3), each=2)) == [1, 1, 2, 2, 3, 3]
    assert list(rep(c(1, 2), length_out=5)) == [1, 2, 1, 2, 1]


def test_length_counts_scalars():
    assert length(c(1, 2, 3)) == 3
    assert length("abc") == 1


def test_sort_unique_rev():
    assert list(sort(c(3, 1, NA, 2))) == [1, 2, 3]
    assert list(sort(c(3, 1, NA, 2), na_last=True)) == [1, 2, 3, NA]
    assert list(sort(c(3, 1, 2), decreasing=True)) == [3, 2, 1]
    assert list(unique(c(1, 1, 2, NA, 2, NA))) == [1, 2, NA]
    assert list(rev(c(1, 2, 3))) == [3, 2, 1]


def test_head_tail():
    nums = c(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    assert list(head(nums)) == [1, 2, 3, 4, 5, 6]
    assert list(tail(nums)) == [5, 6, 7, 8, 9, 10]
    assert list(head(nums, -1)) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert list(tail(nums, 2)) == [9, 10]


def test_which_positions():
    assert list(which(c(False, True, False, True))) == [2, 4]
    assert which_max(c(4, 9, 2)) == 2
    assert which_min(c(4, 9, 2)) == 3


def test_ifelse_and_isin():
    assert list(ifelse(c(1, 5, 9) > 4, "big", "small")) == ["small", "big", "big"]
    assert list(isin(c(1, 2, 7), c(2, 7))) == [False, True, True]
    assert list(isin(10, c(4, 8, 10))) == [True]


def test_type_disagreeing_isin():
    # R keeps booleans and numbers distinct for %in%
    assert list(isin(True, c(1))) == [False]
    assert list(isin(True, c(True))) == [True]


def test_pipe():
    assert pipe(c(1, 2, 3), mean) == 2.0
    assert pipe(2, lambda x: x * 3) == 6
    assert pipe(c(1, 2, 3, 4), sum) == 10


def test_paste():
    assert paste("a", "b", sep="-") == "a-b"
    assert list(paste(c("a", "b"), 1, sep="-")) == ["a-1", "b-1"]
    assert paste(c("a", "b"), c(1, 2), collapse="/") == "a 1/b 2"
    assert list(paste0("x", c(1, 2))) == ["x1", "x2"]


def test_string_tools():
    assert substr("abcdef", 2, 4) == "bcd"
    assert list(substr(c("abcd", "abcde"), 2, 3)) == ["bc", "bc"]
    assert substring("abcdef", 3) == "cdef"
    assert list(nchar(c("ab", "abc"))) == [2, 3]
    assert toupper("ab") == "AB"


def test_table_counts_sorted():
    t = table(c("b", "a", "b"))
    assert list(t.keys()) == ["a", "b"]
    assert t["b"] == 2
    assert "\n" in repr(t)


def test_stats_values():
    assert median(c(1, 2, 3, 4)) == 2.5
    assert sd(c(2, 4, 6, 8)) == pytest.approx(2.581988897471611)
    assert var(c(2, 4, 6, 8)) == pytest.approx(6.6666667, rel=1e-6)
    assert sum(c(1, 2, 3.0)) == 6.0
    assert mean(c(1, 2, 3)) == 2.0


def test_summary_layout():
    s = summary(c(1, 2, 3, 4))
    text = repr(s)
    assert "1st Qu." in text
    assert "1.75" in text
    assert "Median" in text


def test_empty_and_infinite():
    assert min(c()) == math.inf
    assert max(c()) == -math.inf
    assert sum(c()) == 0
    assert math.isnan(sqrt(-1))
    assert log(8, base=2) == pytest.approx(3.0)


def test_sprintf():
    assert sprintf("%d-%s", 5, "x") == "5-x"
