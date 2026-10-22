"""Parity battery: the NumPy backend and the pure-Python backend must agree."""

import pytest

import PyRlang.vector as pv
from PyRlang import NA, c, log, max, mean, median, min, sd, sort, sqrt, sum, unique

v = c(1, 2, 3, 4, 5)
w = c(2, 4.5, 8, 1, 3.3, NA)


def approx(a, b):
    if a is NA or b is NA:
        return a is NA and b is NA
    if isinstance(a, float) and isinstance(b, float):
        if a != a and b != b:  # both NaN
            return True
    return a == b


def assert_vec(result, expected):
    got = [NA if x is NA else x for x in result]
    exp = [NA if x is NA else x for x in expected]
    assert len(got) == len(exp)
    for a, e in zip(got, exp, strict=True):
        assert approx(a, e), (got, exp)


@pytest.fixture(params=["numpy", "pure"])
def backend(request, monkeypatch):
    if request.param == "pure":
        monkeypatch.setattr(pv, "_np", None)
    return request.param


def test_arithmetic(backend):
    assert_vec(v + c(10, 20), [11, 22, 13, 24, 15])
    assert_vec(v * 3, [3, 6, 9, 12, 15])
    assert_vec(10 - v, [9, 8, 7, 6, 5])
    assert_vec(v / c(2, 4), [0.5, 0.5, 1.5, 1.0, 2.5])
    assert_vec(1 / c(2, 0), [0.5, float("inf")])
    assert_vec(v // 2, [0, 1, 1, 2, 2])
    assert_vec(c(7, -7) % 3, [1, 2])
    assert_vec(v**2, [1, 4, 9, 16, 25])
    assert_vec(c(2, 0) ** c(3, -1), [8, float("inf")])
    assert_vec(-v, [-1, -2, -3, -4, -5])
    assert_vec(abs(c(-1, 2.5, NA)), [1, 2.5, NA])


def test_comparisons(backend):
    assert_vec(v > 3, [False, False, False, True, True])
    assert_vec(c(1, 2) == c(1, 9), [True, False])
    assert_vec(w > 3, [False, True, True, False, True, NA])


def test_na_statistics(backend):
    assert mean(w) is NA
    assert mean(w, na_rm=True) == (2 + 4.5 + 8 + 1 + 3.3) / 5
    assert sd(w) is NA
    if backend == "numpy":
        assert sd(w, na_rm=True) == sd(c(2, 4.5, 8, 1, 3.3))
    else:
        assert sd(w, na_rm=True) == sd(c(2, 4.5, 8, 1, 3.3))
    assert median(w, na_rm=True) == median(c(2, 4.5, 8, 1, 3.3))
    assert min(c(1, NA)) is NA
    assert min(c(1, NA), na_rm=True) == 1
    assert max(c()) == -float("inf")
    assert sum(c(1, 2, 3)) == 6


def test_sort_unique(backend):
    assert_vec(sort(c(3, 1, NA, 2)), [1, 2, 3])
    assert_vec(sort(c(3, 1, 2), decreasing=True), [3, 2, 1])
    assert_vec(unique(c(1, 1, 2, 1)), [1, 2])
    assert_vec(unique(c(1, NA, 1)), [1, NA])


def test_math(backend):
    assert_vec(sqrt(c(4, 9, -1)), [2.0, 3.0, float("nan")])
    assert log(8, base=2) == 3.0


def test_logic(backend):
    assert_vec(c(True, False, True, False) & True, [True, False, True, False])
    assert_vec(c(True, False) | c(False, True), [True, True])
    assert_vec(c(True, False, NA) & True, [True, False, NA])
    assert_vec(~c(True, False, 3), [False, True, False])
