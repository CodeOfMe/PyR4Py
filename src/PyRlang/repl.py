"""Interactive PyRlang console: feels like the R prompt, runs on Python."""

from __future__ import annotations

import contextlib
import io
import platform
import sys
import tokenize as _tk

from PyRlang.__version__ import __version__
from PyRlang.funcs import _echo
from PyRlang.transform import PRELUDE, TransformError, transform
from PyRlang.vector import PyRError

__all__ = ["repl"]

_OP_CONTINUATIONS = {
    ":",
    "=",
    ",",
    "+",
    "-",
    "*",
    "/",
    "//",
    "%",
    "%%",
    "**",
    "^",
    "&",
    "|",
    "<",
    ">",
    "<=",
    ">=",
    "==",
    "!=",
    "%in%",
}


def _needs_more(src: str) -> bool:
    """True when src is an incomplete statement and we should keep reading."""
    try:
        toks = list(_tk.generate_tokens(io.StringIO(src).readline))
    except (_tk.TokenError, IndentationError):
        return True
    depth = 0
    for t in toks:
        if t.type == _tk.OP:
            if t.string in "([{":
                depth += 1
            elif t.string in ")]}":
                depth -= 1
    if depth > 0:
        return True
    last = None
    for t in reversed(toks):
        if t.type in (_tk.NL, _tk.COMMENT, _tk.ENDMARKER, _tk.DEDENT):
            continue
        last = t
        break
    if last is None:
        return True
    if last.type == _tk.NEWLINE:
        idx = toks.index(last)
        j = idx - 1
        while j >= 0 and toks[j].type in (_tk.COMMENT, _tk.NL):
            j -= 1
        prev = toks[j] if j >= 0 else None
        if prev is not None and prev.type == _tk.OP and prev.string == ":":
            return True  # a block opener: need the indented body next
        return False
    if last.type == _tk.OP and last.string in _OP_CONTINUATIONS:
        return True
    return False


class PyrConsole:
    """Line-oriented console with R-style echo of expression results."""

    def __init__(self):
        self.ns: dict = {"__name__": "__PyRlang__", "__doc__": None}
        exec(PRELUDE, self.ns)
        self.buf: list[str] = []

    def feed(self, line: str) -> None:
        if self.buf:
            if line.strip() == "":
                src = "\n".join(self.buf) + "\n"
                self.buf.clear()
                self.run(src)
                return
            self.buf.append(line)
            self._flush_when_complete()
            return
        if line.strip() == "":
            return
        if _needs_more(line + "\n"):
            self.buf.append(line)
            return
        self.run(line + "\n")

    def _flush_when_complete(self) -> None:
        src = "\n".join(self.buf) + "\n"
        if not _needs_more(src):
            self.buf.clear()
            self.run(src)

    def run(self, src: str) -> None:
        try:
            py_src = transform(src)
        except TransformError as exc:
            print(f"Error: {exc.args[0] if exc.args else exc}")
            return
        try:
            code = compile(py_src, "<PyRlang>", "single")
        except (SyntaxError, ValueError):
            try:
                code = compile(py_src, "<PyRlang>", "exec")
            except SyntaxError as exc:
                self._syntax(exc)
                return
        try:
            with _r_displayhook(self.ns):
                exec(code, self.ns)
        except SystemExit:
            raise
        except KeyboardInterrupt:
            print()
        except PyRError as exc:
            print(f"Error: {exc}")
        except Exception as exc:  # noqa: BLE001 - console report, not a crash
            print(f"Error: {type(exc).__name__}: {exc}")

    @staticmethod
    def _syntax(exc: SyntaxError) -> None:
        msg = exc.msg or "invalid syntax"
        where = f" at line {exc.lineno}" if exc.lineno else ""
        print(f"Error:{where} {msg}")


@contextlib.contextmanager
def _r_displayhook(ns: dict):
    """Route 'single'-mode echo through R-style printing and keep `_` set."""
    old = sys.displayhook

    def hook(value):
        if value is not None:
            _echo(value)
            ns["_"] = value

    sys.displayhook = hook
    try:
        yield
    finally:
        sys.displayhook = old


def _setup_readline(console: PyrConsole) -> None:
    """Best-effort TAB completion and persistent history (IPython-ish comfort)."""
    if not sys.stdin.isatty() or not hasattr(sys.stdin, "isatty"):
        return
    try:
        import atexit
        import readline
        from pathlib import Path
    except ImportError:
        return
    history_path = Path.home() / ".pyr_history"
    try:
        readline.read_history_file(str(history_path))
    except OSError:
        pass

    names: set[str] = set()
    try:
        import PyRlang as pyrmod  # noqa: N813 - local alias keeps the closure short

        module_names = {n for n in dir(pyrmod) if not n.startswith("_")}
    except Exception:  # noqa: BLE001 - completion must never crash the console
        module_names = set()

    def completer(text: str, state: int):
        if state == 0:
            names.clear()
            names.update(k for k in console.ns if not k.startswith("__"))
            names.update(module_names)
        matches = sorted(k for k in names if k.startswith(text))
        return matches[state] if state < len(matches) else None

    try:
        readline.set_completer(completer)
        readline.set_completer_delims(" \t\n()[]{}=+-*/%<>,;")
        readline.parse_and_bind("tab: complete")
        readline.set_history_length(2000)
        atexit.register(lambda: readline.write_history_file(str(history_path)))
    except (OSError, ValueError):
        pass


def repl() -> None:
    console = PyrConsole()
    _setup_readline(console)
    print(
        f"PyRlang {__version__} on Python {platform.python_version()} — R-style syntax, pure Python"
    )
    print("Try: x <- c(1, 2, 3); mean(x).  TAB completes, _ is the last result,")
    print("q() or Ctrl-D quits, source('file.pyr') runs a script.")
    while True:
        prompt = "+ " if console.buf else ">> "
        try:
            line = input(prompt)
        except EOFError:
            print()
            return
        except KeyboardInterrupt:
            print()
            console.buf.clear()
            continue
        console.feed(line)
