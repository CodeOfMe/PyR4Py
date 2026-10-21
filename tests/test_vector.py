import math

import pytest

from PyRlang import NA, PyRError, c, mean, min


def test_one_based_indexing():
    v = c(1, 2, 3)
    assert v[1] == 1
    assert v[3] == 3
    with pytest.raises(IndexError):
        _ = v[4]
    with pytest.raises(PyRError):
        _ = v[0]


def test_negative_exclusion():
    v = c(10, 20, 30)
    assert list(v[-1]) == [20, 30]
    assert list(v[c(-1, -3)]) == [20]


def test_inclusive_slices_with_na_padding():
    v = c(10, 20, 30, 40, 50)
    assert list(v[2:4]) == [20, 30, 40]
    got = v[1:99]
    assert list(got[:5]) == [10, 20, 30, 40, 50]
    assert got[6] is NA


def test_recycling():
    v = c(1, 2)
    assert list(v + c(10, 20, 30, 40)) == [11, 22, 31, 42]
    assert list(2 * v) == [2, 4]
    assert list(10 - v) == [9, 8]
    assert list(v / c(2, 4)) == [0.5, 0.5]


def test_division_zero_is_infinity_like_r():
    assert list(1 / c(2, 0)) == [0.5, float("inf")]
    assert math.isnan((0 / c(0))[1])


def test_comparisons_are_elementwise():
    v = c(1, 2, 3)
    assert list(v > 2) == [False, False, True]
    assert list(v == c(1, 2, 9)) == [True, True, False]


def test_na_propagation():
    v = c(1, NA, 3)
    assert list(v + 1) == [2, NA, 4]
    assert mean(v) is NA
    assert mean(v, na_rm=True) == 2.0


def test_na_in_min_and_max():
    assert min(c(1, NA)) is NA
    assert min(c(1, NA), na_rm=True) == 1


def test_condition_length_errors():
    with pytest.raises(PyRError):
        bool(c(1, 2))
    with pytest.raises(PyRError):
        bool(c())
    with pytest.raises(PyRError):
        bool(NA)


def test_repr_r_style():
    # R coerces c(1, 2.5, "a") wholly to character: "1" "2.5" "a"
    assert repr(c(1, 2.5, "a")) == '[1] "1" "2.5" "a"'
    assert repr(c(True)) == "[1] TRUE"
    assert repr(c(1, NA, math.inf)) == "[1] 1 NA Inf"


def test_repr_wraps_long_vectors():
    lines = repr(c(range(1, 40))).split("\n")
    assert lines[0].startswith("[1] ")
    assert len(lines) > 1
    assert lines[1].startswith("[")


def test_logical_selection():
    v = c(10, 20, 30)
    assert list(v[c(True, False, True)]) == [10, 30]
    assert list(v[v > 15]) == [20, 30]


def test_setitem_grows_with_na():
    v = c(1)
    v[3] = 9
    assert list(v) == [1, NA, 9]


def test_invert_is_elementwise_not():
    assert list(~c(True, False)) == [False, True]


def test_amp_logic_with_na():
    v = c(True, False, NA)
    assert list(v & True) == [True, False, NA]
    assert list(c(True, False) | c(False, False)) == [True, False]
