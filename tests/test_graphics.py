"""Optional graphics on matplotlib + pandas interop."""

import pytest

from PyRlang import NA, PyRError, Vector, c

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from PyRlang.graphics import barplot, hist, plot  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_counter(monkeypatch):
    import PyRlang.graphics as g

    monkeypatch.setattr(g, "_FIG_NO", 0)


def test_plot_saves_png(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fig = plot(c(1, 4, 9), col="steelblue")
    assert (tmp_path / "plot_01.png").exists()
    assert fig is not None


def test_hist_saves_png(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hist(c(1, 1, 2, 2, 2, 3), breaks=3)
    assert (tmp_path / "hist_01.png").exists()


def test_barplot_names(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    barplot(c(2, 5), names_arg=c("a", "b"))
    assert (tmp_path / "barplot_01.png").exists()


def test_na_dropped_and_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plot(Vector([1, NA, 3]))
    with pytest.raises(PyRError):
        plot(c("a", "b"))


def test_to_pandas_roundtrip():
    pd = pytest.importorskip("pandas")
    from PyRlang import data_frame, from_pandas, to_pandas

    df = data_frame(a=c(1, 2), b=c(1.5, NA))
    p = to_pandas(df)
    assert isinstance(p, pd.DataFrame)
    assert list(p["a"]) == [1, 2]
    assert p["b"].isna().tolist() == [False, True]
    back = from_pandas(p)
    assert back.colnames == ["a", "b"]
    assert list(back.a) == [1, 2]
    assert back.b[2] is NA
