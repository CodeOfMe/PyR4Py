import pytest

from PyRlang.transform import TransformError


def test_assign_adjacent(tx):
    assert tx("x <- 1") == "x = 1"
    assert tx("x <- -5") == "x = -5"
    assert tx("x <- 5; y <- f(1:3)") == "x = 5; y = f(seq(1, 3))"


def test_spaced_compare_untouched(tx):
    assert tx("x < -1") == "x < -1"
    assert tx("if (a < -b):\n    pass") == "if (a < -b):\n    pass"


def test_doubles_and_pairs(tx):
    assert tx("a && b") == "a and b"
    assert tx("a || b") == "a or b"
    assert tx("2 ^ 10") == "2 ** 10"
    assert tx("7 %% 2") == "7 % 2"


def test_dollar_and_dotted_names(tx):
    assert tx("df$a$b2 <- 3") == "df.a.b2 = 3"
    assert tx("data.frame(a = 1)") == "data_frame(a = 1)"
    assert tx("mean(x, na.rm = TRUE)") == "mean(x, na_rm = TRUE)"
    assert tx("which.max(v)") == "which_max(v)"
    assert tx("seq(1, 10, length.out = 4)") == "seq(1, 10, length_out = 4)"


def test_colon_rules(tx):
    assert tx("x = 1:10") == "x = seq(1, 10)"
    assert tx("v[1:3]") == "v[1:3]"
    assert tx("f = lambda x: x + 1") == "f = lambda x: x + 1"
    assert tx("def h(x: int):\n    return x") == "def h(x: int):\n    return x"
    assert tx("def h(x: int = 2):\n    return x") == "def h(x: int = 2):\n    return x"
    assert tx("d = {'k': 1}") == "d = {'k': 1}"
    assert tx("z: int = 2") == "z: int = 2"
    assert tx("for i in 1:3:\n    pass") == "for i in seq(1, 3):\n    pass"
    assert tx("total = sum(1:10)") == "total = sum(seq(1, 10))"


def test_pipe(tx):
    assert tx("c(1,2) %>% mean()") == "PyRlang.pipe(c(1,2), mean)"
    assert tx("x |> mean()") == "PyRlang.pipe(x, mean)"
    assert tx("x %>% head(2)") == "PyRlang.pipe(x, head, 2)"
    assert tx("1:10 %>% sum()") == "PyRlang.pipe(seq(1, 10), sum)"


def test_pipe_chain(tx):
    src = "x <- 1:5 %>% mean() %>% sum()"
    once = tx(src)
    assert once == "x = PyRlang.pipe(PyRlang.pipe(seq(1, 5), mean), sum)"
    assert tx(once) == once


def test_isin(tx):
    assert tx("a %in% b") == "PyRlang.isin(a, b)"
    assert tx("c(1,2) %in% c(1,3)") == "PyRlang.isin(c(1,2), c(1,3))"


def test_formula(tx):
    assert tx("y ~ x + 1") == "Formula('y ~ x + 1')"
    assert tx("f <- wage ~ age") == "f = Formula('wage ~ age')"
    assert tx("g(y ~ x, d)") == "g(Formula('y ~ x'), d)"


def test_not(tx):
    assert tx("!TRUE") == "PyRlang.not_(TRUE)"
    assert tx("!c(1, 2)") == "PyRlang.not_(c(1, 2))"
    assert tx("!x & y") == "PyRlang.not_(x) & y"


def test_global_assign_rejected(tx):
    with pytest.raises(TransformError):
        tx("x <<- 5")


def test_plain_python_untouched(tx):
    src = "x = 3\ny = [1, 2]\nprint(x, y)"
    assert tx(src) == src


def test_exec_assign_and_range(exec_r):
    ns = exec_r("x <- 1:3\ny <- x + 10")
    assert list(ns["y"]) == [11, 12, 13]


def test_exec_pipe(exec_r):
    ns = exec_r("r <- 1:10 %>% sum()")
    assert ns["r"] == 55


def test_exec_not_vectorised(exec_r):
    ns = exec_r("r <- !c(TRUE, TRUE, FALSE)")
    assert list(ns["r"]) == [False, False, True]


def test_exec_formula(exec_r):
    ns = exec_r("mod <- y ~ x + 1")
    assert repr(ns["mod"]) == "y ~ x + 1"


def test_exec_dataframe_syntax(exec_r):
    ns = exec_r("d <- data.frame(age = c(30, 50))\nr <- d$age %>% mean()")
    assert ns["r"] == 40.0


def test_exec_na_rm(exec_r):
    ns = exec_r("r <- mean(c(1, NA, 3), na.rm = TRUE)")
    assert ns["r"] == 2.0


def test_exec_native_pipe(exec_r):
    ns = exec_r("r <- c('a', 'b') |> toupper()")
    assert list(ns["r"]) == ["A", "B"]


def test_exec_ifelse_and_isin(exec_r):
    ns = exec_r("a <- ifelse(c(1, 5, 9) > 4, 'big', 'small')\nb <- 10 %in% c(4, 8, 10)")
    assert list(ns["a"]) == ["small", "big", "big"]
    assert list(ns["b"]) == [True]
