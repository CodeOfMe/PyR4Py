"""Command-line entry points: ``PyRlang script.pyr``, ``PyRlang -e CODE``, ``PyRlang`` (REPL)."""

from __future__ import annotations

import argparse
import sys

from PyRlang.__version__ import __version__
from PyRlang.transform import PRELUDE, TransformError, transform

__all__ = ["main", "run_source"]

_PRELUDE_LINES = PRELUDE.count("\n")


def run_source(src: str, filename: str, argv_rest: list[str] | None = None) -> None:
    """Compile & run R-flavoured source with top-level echo like the R console."""
    argv_rest = argv_rest or []
    try:
        py_src = transform(src, autoprint=True)
    except TransformError as exc:
        print(f"PyRlang: {exc.args[0] if exc.args else exc}", file=sys.stderr)
        raise SystemExit(2) from None
    try:
        code = compile(PRELUDE + py_src, filename, "exec")
    except SyntaxError as exc:
        line = exc.lineno - _PRELUDE_LINES if exc.lineno else None
        where = f" at line {line}" if line else ""
        print(f"PyRlang: syntax error in {filename}{where}: {exc.msg}", file=sys.stderr)
        raise SystemExit(2) from None
    namespace = {
        "__name__": "__main__",
        "__file__": filename if not filename.startswith("<") else "<PyRlang>",
    }
    old_argv = sys.argv
    sys.argv = [filename] + list(argv_rest)
    try:
        exec(code, namespace)
    finally:
        sys.argv = old_argv


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="PyRlang",
        description="PyRlang — R-style syntax for pure Python",
    )
    parser.add_argument(
        "script",
        nargs="?",
        help="a .pyr script (R-flavoured Python) to run",
    )
    parser.add_argument(
        "-e",
        "--eval",
        dest="eval_code",
        metavar="CODE",
        help="run CODE and echo top-level results like R",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"PyRlang {__version__} (PyPI: pyr4py)",
    )
    args, rest = parser.parse_known_args(argv)

    if args.eval_code is not None:
        run_source(args.eval_code, "<PyRlang -e>", rest)
        return

    if args.script is not None:
        try:
            with open(args.script, encoding="utf-8") as fh:
                src = fh.read()
        except OSError as exc:
            print(f"PyRlang: cannot open {args.script}: {exc.strerror or exc}", file=sys.stderr)
            raise SystemExit(2) from None
        run_source(src, args.script, rest)
        return

    from PyRlang.repl import repl

    repl()


if __name__ == "__main__":  # pragma: no cover
    main()
