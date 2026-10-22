"""R-terminal REPL features: `_` last value, q(), source()."""

import pytest

from PyRlang.repl import PyrConsole


def test_last_value_underscore():
    console = PyrConsole()
    console.feed("x <- 1:3")
    console.feed("sum(x)")
    assert console.ns["_"] == 6
    console.feed("mean(x)")
    assert console.ns["_"] == 2.0


def test_q_exits():
    console = PyrConsole()
    with pytest.raises(SystemExit):
        console.run("q()")


def test_source_runs_script_into_namespace(tmp_path):
    script = tmp_path / "script.pyr"
    script.write_text("v <- 1:3\ns <- sum(v)\n", encoding="utf-8")
    console = PyrConsole()
    console.feed(f"source('{script}')")
    assert console.ns["s"] == 6
    assert list(console.ns["v"]) == [1, 2, 3]
