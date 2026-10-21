import pytest

from PyRlang import NA, DataFrame, PyRError, c, data_frame, names, ncol, nrow, read_csv, write_csv


def make_df():
    return data_frame(
        name=c("ada", "bob", "clyde", "dana"),
        age=c(34, 47, 29, 41),
        wage=c(21.5, 33.0, 18.2, 29.4),
    )


def test_attr_access():
    df = make_df()
    assert list(df.age) == [34, 47, 29, 41]
    with pytest.raises(AttributeError):
        _ = df.nope


def test_row_filter_r_style():
    df = make_df()
    sub = df[df.age > 30,]
    assert nrow(sub) == 3
    assert list(sub.name) == ["ada", "bob", "dana"]


def test_rows_and_cols():
    df = make_df()
    sub = df[df.age > 30, c("name", "wage")]
    assert sub.colnames == ["name", "wage"]
    assert list(sub.wage) == [21.5, 33.0, 29.4]


def test_all_rows_one_col_gives_vector():
    df = make_df()
    got = df[:, "age"]
    assert list(got) == [34, 47, 29, 41]


def test_string_key_is_one_column_frame():
    df = make_df()
    one = df["age"]
    assert isinstance(one, DataFrame)
    assert ncol(one) == 1


def test_int_vector_selects_columns():
    df = make_df()
    two = df[c(1, 3)]
    assert two.colnames == ["name", "wage"]


def test_setattr_adds_column():
    df = make_df()
    df.senior = df.age > 40
    assert list(df.senior) == [False, True, False, True]


def test_scalar_assignment_recycles():
    df = make_df()
    df.flag = True
    assert list(df.flag) == [True, True, True, True]


def test_names_and_shape():
    df = make_df()
    assert list(names(df)) == ["name", "age", "wage"]
    assert nrow(df) == 4
    assert ncol(df) == 3


def test_row_out_of_bounds():
    df = make_df()
    with pytest.raises(IndexError):
        _ = df[9,]


def test_repr_layout():
    df = make_df()
    lines = repr(df).split("\n")
    assert "name" in lines[0] and "age" in lines[0] and "wage" in lines[0]
    assert lines[1].startswith("1")
    assert "ada" in lines[1]


def test_csv_roundtrip(tmp_path):
    df = make_df()
    target = tmp_path / "people.csv"
    write_csv(df, target)
    back = read_csv(target)
    assert back.colnames == ["name", "age", "wage"]
    assert list(back.age) == [34, 47, 29, 41]
    assert list(back.wage) == [21.5, 33.0, 18.2, 29.4]


def test_csv_na_roundtrip(tmp_path):
    target = tmp_path / "with_na.csv"
    write_csv(data_frame(x=c(1, NA, 3)), target)
    back = read_csv(target)
    assert back.x[2] is NA
    assert list(back.x) == [1, NA, 3]


def test_bad_column_lengths():
    with pytest.raises(PyRError):
        data_frame(a=c(1, 2), b=c(1, 2, 3))
