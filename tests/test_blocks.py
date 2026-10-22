"""R brace-block syntax translated into Python indentation."""

import pytest

from PyRlang.transform import TransformError

IF_ELSE = """\
msg <- "unset"
if (total > 10) {
  msg <- "big"
} else if (total == 10) {
  msg <- "ten"
} else {
  msg <- "small"
}
"""


def test_if_else_if_else(exec_r):
    ns = exec_r("total <- 10\n" + IF_ELSE)
    assert ns["msg"] == "ten"


def test_if_branch_taken(exec_r):
    ns = exec_r("total <- 99\n" + IF_ELSE)
    assert ns["msg"] == "big"


def test_else_branch_taken(exec_r):
    ns = exec_r("total <- 1\n" + IF_ELSE)
    assert ns["msg"] == "small"


def test_for_loop_block(exec_r):
    ns = exec_r("total <- 0\nfor (i in 1:5) {\n  total <- total + i\n}")
    assert ns["total"] == 15


def test_while_block(exec_r):
    ns = exec_r("total <- 8\nwhile (total > 0) {\n  total <- total - 3\n}")
    assert ns["total"] == -1


def test_repeat_with_break(exec_r):
    ns = exec_r(
        "guard <- 0\nrepeat {\n  guard <- guard + 3\n  if (guard >= 9) {\n    break\n  }\n}"
    )
    assert ns["guard"] == 9


def test_next_skips(exec_r):
    ns = exec_r(
        "odds <- 0\nfor (i in 1:9) {\n  if (i %% 2 == 0) {\n    next\n  }\n  odds <- odds + 1\n}"
    )
    assert ns["odds"] == 5


def test_nested_blocks(exec_r):
    ns = exec_r(
        "acc <- 0\nfor (i in 1:3) {\n  for (j in 1:3) {\n"
        "    if (i * j == 6) {\n      acc <- acc + 100\n    }\n  }\n}"
    )
    assert ns["acc"] == 200


def test_header_transform_text(tx):
    src = "if (x > 2) {\n  y <- 1\n} else {\n  y <- 2\n}"
    assert tx(src) == "if x > 2:\n    y = 1\nelse:\n    y = 2"


def test_block_with_pipes_inside(exec_r):
    ns = exec_r("v <- 1:4 %>% mean()\nr <- 0\nfor (i in 1:3) {\n  r <- r + v\n}")
    assert ns["v"] == 2.5
    assert ns["r"] == 7.5


def test_python_code_outside_braces_untouched(tx):
    src = "for i in seq(1, 3):\n    pass\nx = {'a': 1}"
    assert tx(src) == src


def test_function_definition_rejected(tx):
    with pytest.raises(TransformError):
        tx("square <- function(x) {\n  x ^ 2\n}")


def test_unclosed_block_rejected(tx):
    with pytest.raises(TransformError):
        tx("if (x) {\n  y <- 1\n")
