import pytest

from PyRlang.transform import PRELUDE, transform


@pytest.fixture
def exec_r():
    """Execute R-flavoured source and return the resulting namespace."""

    def run(src: str) -> dict:
        ns = {"__name__": "__PyRlang__"}
        exec(PRELUDE + transform(src), ns)
        return ns

    return run


@pytest.fixture
def tx():
    return transform
