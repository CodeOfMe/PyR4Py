"""Transform R-flavoured source into pure Python.

Only used in *transform mode* — files run via ``python -m PyRlang``, ``PyRlang -e``,
or the interactive REPL.  Plain ``.py`` files never see this.

Rules (mirroring the real R parser where they differ from Python):

=============  ==========================  ==================================
R syntax       becomes                     notes
=============  ==========================  ==================================
``x <- e``     ``x = e``                   only when ``<`` and ``-`` are
                                           adjacent (RParser rule); ``a < -b``
                                           with a space stays a comparison
``<<-``        not supported               raises TransformError
``a && b``     ``a and b``                 adjacent pair only
``a || b``     ``a or b``                  adjacent pair only
``!x``         ``PyRlang.not_(x)``             element-wise R negation
``a:b``        ``seq(a, b)``               outside ``[]``/``{}``; not after
                                           lambda/def-param colons, not
                                           annotations
``x ^ y``      ``x ** y``
``x %% y``     ``x % y``
``a %in% b``   ``PyRlang.isin(a, b)``
``a %>% f(b)`` ``PyRlang.pipe(a, f, b)``       magrittr; ``|>`` also handled
``y ~ x + z``  ``Formula('y ~ x + z')``
``df$col``     ``df.col``
``data.frame`` ``DataFrame``               also read.csv/write.csv,
                                           which.max/which.min,
                                           na.rm=, length.out=
=============  ==========================  ==================================
"""

from __future__ import annotations

import ast
import io
import keyword as _keyword
import tokenize as _tk

PRELUDE = "from PyRlang import *\nimport PyRlang\n"

_KEYWORDS = frozenset(_keyword.kwlist)

_DOTTED = {
    ("data", "frame"): "data_frame",
    ("read", "csv"): "read_csv",
    ("write", "csv"): "write_csv",
    ("which", "max"): "which_max",
    ("which", "min"): "which_min",
    ("na", "rm"): "na_rm",
    ("length", "out"): "length_out",
    ("names", "arg"): "names_arg",
}

_DOTTED_FIRST = {first for first, _ in _DOTTED}

_STOP_LEFT = frozenset({";", ",", "(", "[", "{", "=", ":", "<", "&", "|", "^", "%", ":="})
_STOP_RIGHT = frozenset({";", ",", ")", "]", "}", "=", ":", ":=", "<", "<=", ">", ">=", "==", "!="})

_SKIP_COLON_PREV2 = frozenset(
    {
        "if",
        "while",
        "else",
        "elif",
        "try",
        "except",
        "finally",
        "with",
        "def",
        "class",
        "lambda",
        "match",
        "case",
        "return",
        "assert",
        "del",
        "pass",
        "break",
        "continue",
        "raise",
        "global",
        "nonlocal",
        "import",
        "from",
        "as",
        "yield",
        "await",
        "not",
        "and",
        "or",
        "is",
    }
)

_SOFT_LINE_START = frozenset({"else", "elif", "try", "finally", "except"})

__all__ = ["PRELUDE", "TransformError", "transform"]


class TransformError(SyntaxError):
    """Raised when R-flavoured source cannot be transformed."""


def _prepass_dollar(src: str) -> str:
    """Replace R's ``obj$field`` with attribute access, leaving strings alone."""
    out: list[str] = []
    i = 0
    n = len(src)
    quote: str | None = None
    while i < n:
        ch = src[i]
        out.append(ch)
        if quote:
            if ch == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            continue
        if ch == "$":
            prev = out[-2] if len(out) >= 2 else ""
            nxt = src[i + 1] if i + 1 < n else ""
            prev_ok = prev.isalnum() or prev in "_)]"
            next_ok = nxt.isalnum() or nxt == "_"
            if prev_ok and next_ok:
                out[-1] = "."
            i += 1
            continue
        i += 1
    return "".join(out)


class _Scan:
    def __init__(self, src: str):
        self.src = src
        try:
            self.toks = list(_tk.generate_tokens(io.StringIO(src).readline))
        except (_tk.TokenError, IndentationError) as exc:
            raise TransformError(f"cannot parse PyRlang source: {exc}") from None
        offsets = [0]
        for line in src.splitlines(keepends=True):
            offsets.append(offsets[-1] + len(line))
        self._offsets = offsets
        n = len(self.toks)
        self.enclose: list[int | None] = [None] * n
        stack: list[int] = []
        for idx, t in enumerate(self.toks):
            self.enclose[idx] = stack[-1] if stack else None
            if t.type == _tk.OP:
                if t.string in "([{":
                    stack.append(idx)
                elif t.string in ")]}" and stack:
                    stack.pop()
        self.def_params: set[int] = set()
        for idx, t in enumerate(self.toks):
            if t.type != _tk.OP or t.string != "(":
                continue
            a = idx - 1
            while a >= 0 and self.toks[a].type == _tk.COMMENT:
                a -= 1
            if a < 0 or self.toks[a].type != _tk.NAME or self.toks[a].string in _KEYWORDS:
                continue
            b = a - 1
            while b >= 0 and self.toks[b].type == _tk.COMMENT:
                b -= 1
            if b >= 0 and self.toks[b].type == _tk.NAME and self.toks[b].string == "def":
                self.def_params.add(idx)

    def off(self, pos) -> int:
        row, col = pos
        idx = row - 1
        if idx < 0:
            return 0
        if idx >= len(self._offsets):
            return len(self.src)
        return self._offsets[idx] + col

    def raw(self, start_idx: int, end_idx: int) -> str:
        a = self.off(self.toks[start_idx].start)
        b = self.off(self.toks[end_idx].end)
        return self.src[a:b]

    def left_start(self, i: int) -> int:
        """Index of the first token of the operand ending right before ``i``."""
        depth = 0
        toks = self.toks
        j = i - 1
        while j >= 0:
            t = toks[j]
            ty, s = t.type, t.string
            if ty == _tk.COMMENT:
                j -= 1
                continue
            if ty == _tk.OP:
                if s in ")]}":
                    depth += 1
                elif s in "([{":
                    if depth == 0:
                        return j + 1
                    depth -= 1
                elif depth == 0 and s in _STOP_LEFT:
                    return j + 1
            elif depth == 0:
                if ty in (_tk.NEWLINE, _tk.INDENT, _tk.DEDENT):
                    return j + 1
                if ty == _tk.NAME and s in _KEYWORDS:
                    return j + 1
            j -= 1
        return 0

    def right_end(self, i: int, extra_stops=frozenset()) -> int:
        """Exclusive end index of the operand starting at token ``i``."""
        depth = 0
        toks = self.toks
        k = i
        n = len(toks)
        while k < n:
            t = toks[k]
            ty, s = t.type, t.string
            if ty == _tk.COMMENT:
                return k
            if ty == _tk.OP:
                if s in "([{":
                    depth += 1
                elif s in ")]}":
                    if depth == 0:
                        return k
                    depth -= 1
                elif depth == 0 and (s in _STOP_RIGHT or s in extra_stops):
                    return k
            elif depth == 0:
                if ty in (_tk.NEWLINE, _tk.NL, _tk.ENDMARKER, _tk.INDENT, _tk.DEDENT):
                    return k
                if ty == _tk.NAME and s in _KEYWORDS:
                    return k
            k += 1
        return k

    def sig_after(self, i: int, across_lines: bool = False) -> int:
        """Index of the next significant token after ``i`` (len == EOF sentinel)."""
        j = i + 1
        n = len(self.toks)
        skip = {_tk.COMMENT, _tk.NL, _tk.INDENT, _tk.DEDENT}
        if across_lines:
            skip |= {_tk.NEWLINE}
        while j < n and self.toks[j].type in skip:
            j += 1
        return j


def _call_end(scan: _Scan, open_idx: int) -> int | None:
    """Matching close-paren index for the ``(`` at open_idx, else None."""
    toks = scan.toks
    n = len(toks)
    depth = 0
    m = open_idx
    while m < n:
        t = toks[m]
        if t.type == _tk.OP:
            if t.string in "([{":
                depth += 1
            elif t.string in ")]}":
                depth -= 1
                if depth == 0:
                    return m
        m += 1
    return None


def _pipe_edit(scan: _Scan, i: int, last_op_idx: int):
    toks = scan.toks
    n = len(toks)
    j = scan.sig_after(last_op_idx, across_lines=True)
    if j >= n or toks[j].type != _tk.NAME or toks[j].string in _KEYWORDS:
        raise TransformError("the right side of a pipe must be a function name or call")
    k = scan.sig_after(j, across_lines=True)
    if k < n and toks[k].type == _tk.OP and toks[k].string == "(":
        close = _call_end(scan, k)
        if close is None:
            raise TransformError("unbalanced parentheses in the piped call")
        end_idx = close
        inner_start = k + 1
    else:
        end_idx = j
        inner_start = None
    left_start_idx = scan.left_start(i)
    if left_start_idx >= i:
        raise TransformError("nothing to pipe on the left side of %>%")
    left_raw = scan.raw(left_start_idx, i - 1).strip()
    func_name = toks[j].string
    if inner_start is None:
        replacement = f"PyRlang.pipe({left_raw}, {func_name})"
    else:
        inner = scan.raw(inner_start, end_idx - 1).strip()
        if inner:
            replacement = f"PyRlang.pipe({left_raw}, {func_name}, {inner})"
        else:
            replacement = f"PyRlang.pipe({left_raw}, {func_name})"
    a = scan.off(toks[left_start_idx].start)
    b = scan.off(toks[end_idx].end)
    return (a, b, replacement)


def _isin_edit(scan: _Scan, i: int):
    toks = scan.toks
    n = len(toks)
    left_start_idx = scan.left_start(i)
    if left_start_idx >= i:
        raise TransformError("nothing on the left side of %in%")
    kk = scan.sig_after(i + 2, across_lines=True)
    if kk >= n:
        raise TransformError("nothing on the right side of %in%")
    end_idx = scan.right_end(kk)
    if end_idx <= kk:
        raise TransformError("nothing on the right side of %in%")
    left_raw = scan.raw(left_start_idx, i - 1).strip()
    right_raw = scan.raw(kk, end_idx - 1).strip()
    a = scan.off(toks[left_start_idx].start)
    b = scan.off(toks[end_idx - 1].end)
    return (a, b, f"PyRlang.isin({left_raw}, {right_raw})")


def _formula_edit(scan: _Scan, i: int):
    toks = scan.toks
    left_idx = scan.left_start(i)
    kk = scan.sig_after(i, across_lines=True)
    end_idx = scan.right_end(kk)
    if end_idx <= kk:
        raise TransformError("formula right side is empty")
    start_tok = toks[left_idx] if left_idx < i else toks[i]
    a = scan.off(start_tok.start)
    b = scan.off(toks[end_idx - 1].end)
    cleaned = " ".join(scan.src[a:b].split())
    return (a, b, f"Formula({cleaned!r})")


def _not_edit(scan: _Scan, i: int):
    toks = scan.toks
    n = len(toks)
    kk = scan.sig_after(i, across_lines=True)
    if kk >= n:
        return None
    end_idx = scan.right_end(kk, extra_stops={"&", "|"})
    if end_idx <= kk:
        return None
    operand = scan.raw(kk, end_idx - 1).strip()
    return (
        scan.off(toks[i].start),
        scan.off(toks[end_idx - 1].end),
        f"PyRlang.not_({operand})",
    )


def _has_lambda_before(scan: _Scan, start_idx: int) -> bool:
    toks = scan.toks
    depth = 0
    j = start_idx
    while j >= 0:
        t = toks[j]
        ty, s = t.type, t.string
        if ty == _tk.COMMENT:
            j -= 1
            continue
        if ty == _tk.OP:
            if s in ")]}":
                depth += 1
            elif s in "([{":
                if depth == 0:
                    return False
                depth -= 1
            elif depth == 0 and s in _STOP_LEFT:
                return False
        elif depth == 0:
            if ty in (_tk.NEWLINE, _tk.INDENT, _tk.DEDENT):
                return False
            if ty == _tk.NAME and s == "lambda":
                return True
        j -= 1
    return False


def _colon_edit(scan: _Scan, i: int):
    """Turn R's ``a:b`` into seq(a, b) where it cannot mean something else."""
    toks = scan.toks
    n = len(toks)
    enc = scan.enclose[i]
    if enc is not None:
        enc_s = toks[enc].string
        if enc_s in "[{" or enc in scan.def_params:
            return None
    # left operand: one NAME or NUMBER on the same line
    p1 = None
    j = i - 1
    while j >= 0:
        t = toks[j]
        if t.type == _tk.COMMENT or t.type == _tk.DEDENT:
            j -= 1
            continue
        if t.type in (_tk.NEWLINE, _tk.NL, _tk.INDENT):
            break
        p1 = j
        break
    if p1 is None or toks[p1].start[0] != toks[i].start[0]:
        return None
    t1 = toks[p1]
    if t1.type not in (_tk.NAME, _tk.NUMBER):
        return None
    if t1.type == _tk.NUMBER:
        pass  # a number on the left is always a range: 1:10
    else:
        p2 = None
        j = p1 - 1
        while j >= 0:
            t = toks[j]
            if t.type == _tk.COMMENT or t.type == _tk.DEDENT:
                j -= 1
                continue
            if t.type in (_tk.NEWLINE, _tk.NL, _tk.INDENT):
                p2 = None
                break
            p2 = j
            break
        if p2 is not None:
            s2 = toks[p2].string
            if s2 == "lambda" or s2 in _SKIP_COLON_PREV2:
                return None
        else:
            # colon at the start of a statement: keep annotations/one-liners
            if t1.string in _SOFT_LINE_START:
                return None
            nn = scan.sig_after(p1)
            if nn >= n or toks[nn].type != _tk.NAME:
                return None
            after = scan.sig_after(nn)
            if after < n:
                ts = toks[after]
                if ts.type == _tk.OP and ts.string in ("=", ":=", "("):
                    return None  # x: int = 1   /   else: call(...)
        if _has_lambda_before(scan, p1):
            return None
    # right operand: one NAME or NUMBER on the same line
    n1 = scan.sig_after(i)
    if n1 >= n:
        return None
    t2 = toks[n1]
    if t2.type not in (_tk.NAME, _tk.NUMBER) or t2.string in _KEYWORDS:
        return None
    if t2.start[0] != toks[i].start[0]:
        return None
    a = scan.off(t1.start)
    b = scan.off(t2.end)
    return (a, b, f"seq({scan.raw(p1, p1).strip()}, {scan.raw(n1, n1).strip()})")


def _dotted_edit(scan: _Scan, i: int):
    toks = scan.toks
    n = len(toks)
    if i + 2 >= n:
        return None
    dot = toks[i + 1]
    nxt = toks[i + 2]
    if dot.type != _tk.OP or dot.string != "." or nxt.type != _tk.NAME:
        return None
    mapped = _DOTTED.get((toks[i].string, nxt.string))
    if mapped is None:
        return None
    a = scan.off(toks[i].start)
    b = scan.off(nxt.end)
    return (a, b, mapped)


def _find_edit(scan: _Scan):
    toks = scan.toks
    n = len(toks)
    for i, t in enumerate(toks):
        ty, s = t.type, t.string
        if ty != _tk.OP:
            if ty == _tk.NAME and s in _DOTTED_FIRST:
                edit = _dotted_edit(scan, i)
                if edit:
                    return edit
            if ty == _tk.NAME and s == "next":
                # R's `next` inside loops -> continue; keep df$next / next(x)
                prev = toks[i - 1] if i else None
                nxt = scan.sig_after(i)
                if not (prev is not None and prev.type == _tk.OP and prev.string == "."):
                    if nxt >= n or not (toks[nxt].type == _tk.OP and toks[nxt].string == "("):
                        return (scan.off(t.start), scan.off(t.end), "continue")
            continue
        nxt = toks[i + 1] if i + 1 < n else None
        nxt2 = toks[i + 2] if i + 2 < n else None
        if s == "<":
            if nxt and nxt.type == _tk.OP and nxt.string == "-" and nxt.start == t.end:
                if nxt2 and nxt2.type == _tk.OP and nxt2.string == "-" and nxt2.start == nxt.end:
                    raise TransformError(
                        "'<<-' is not supported; plain '<-' already writes to script scope"
                    )
                return (scan.off(t.start), scan.off(nxt.end), "=")
        elif s == "<<":
            # R's <<- is lexed as '<<' '-' by Python's tokenizer
            if nxt and nxt.type == _tk.OP and nxt.string == "-" and nxt.start == t.end:
                raise TransformError(
                    "'<<-' is not supported; plain '<-' already writes to script scope"
                )
        elif s == "&":
            if nxt and nxt.type == _tk.OP and nxt.string == "&" and nxt.start == t.end:
                return (scan.off(t.start), scan.off(nxt.end), "and")
        elif s == "|":
            if nxt and nxt.type == _tk.OP and nxt.start == t.end:
                if nxt.string == "|":
                    return (scan.off(t.start), scan.off(nxt.end), "or")
                if nxt.string == ">":
                    return _pipe_edit(scan, i, i + 1)
        elif s == "%":
            if nxt and nxt.type == _tk.OP and nxt.start == t.end:
                if (
                    nxt.string == ">"
                    and nxt2
                    and nxt2.type == _tk.OP
                    and nxt2.string == "%"
                    and nxt2.start == nxt.end
                ):
                    return _pipe_edit(scan, i, i + 2)
                if nxt.string == "%":
                    return (scan.off(t.start), scan.off(nxt.end), "%")
            if nxt and nxt.type == _tk.NAME and nxt.string == "in" and nxt.start == t.end:
                if nxt2 and nxt2.type == _tk.OP and nxt2.string == "%" and nxt2.start == nxt.end:
                    return _isin_edit(scan, i)
        elif s == "^":
            return (scan.off(t.start), scan.off(t.end), "**")
        elif s == "~":
            return _formula_edit(scan, i)
        elif s == ":":
            edit = _colon_edit(scan, i)
            if edit:
                return edit
        elif s == "!":
            edit = _not_edit(scan, i)
            if edit:
                return edit
    return None


def _split_comment(line: str):
    """Split one line into (code, comment); quote-aware."""
    out = []
    i = 0
    n = len(line)
    quote = None
    while i < n:
        ch = line[i]
        if quote:
            if ch == "\\" and i + 1 < n:
                out.append(line[i : i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
            out.append(ch)
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "#":
            return "".join(out), line[i:]
        out.append(ch)
        i += 1
    return "".join(out), ""


def _balanced_paren(text: str):
    """If text is exactly one '(…)' pair, return the inside; otherwise None."""
    stripped = text.strip()
    if not stripped.startswith("("):
        return None
    depth = 0
    quote = None
    i = 0
    n = len(stripped)
    while i < n:
        ch = stripped[i]
        if quote:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                inside = stripped[1:i]
                tail = stripped[i + 1 :].strip()
                return inside if not tail else None
        i += 1
    return None


def _split_for_tokens(inside: str):
    """Split ``i in 1:10`` into ('i', '1:10') at the first top-level ' in '."""
    depth = 0
    quote = None
    i = 0
    n = len(inside)
    while i < n:
        ch = inside[i]
        if quote:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == " " and depth == 0 and inside[i : i + 4] == " in ":
            var = inside[:i].strip()
            seq = inside[i + 4 :].strip()
            if var and seq:
                return var, seq
            return None
        i += 1
    return None


def _convert_blocks(src: str) -> str:
    """Translate R brace blocks into Python indentation.

    ``if (c) {`` / ``} else {`` / ``} else if (c) {`` / ``for (i in s) {`` /
    ``while (c) {`` / ``repeat {`` become python headers; the matching lone
    ``}`` line is removed and body lines are re-indented one level per open
    ``{``.  Lines at brace depth 0 are left byte-identical, so python-style
    code that also lives in ``.pyr`` files is never reshaped.
    """
    out = []
    depth = 0
    rblocks: list[bool] = []  # per open brace: True = an R block we converted
    quote = None
    for line in src.split("\n"):
        if quote is not None:
            out.append(line)
            code, _ = _split_comment(line)
            for ch in code:
                if quote:
                    if ch == "\\":
                        continue
                    if ch == quote:
                        quote = None
                elif ch in "\"'":
                    quote = ch
            continue
        code, comment = _split_comment(line)
        core = code.rstrip()
        stripped = core.lstrip()
        suffix = (" " + comment.rstrip()) if comment else ""
        if not stripped:
            out.append(line)
            continue
        indent = "    " * depth

        if stripped == "}" and rblocks and rblocks[-1]:
            depth -= 1
            rblocks.pop()
            if depth < 0:
                raise TransformError("unbalanced '}': no R block is open")
            continue
        if stripped.startswith("}") and not stripped.endswith("{"):
            depth -= 1
            if rblocks:
                rblocks.pop()
            out.append(("    " * max(depth, 0)) + stripped + suffix)
            continue
        if stripped.endswith("{"):
            head = stripped[:-1].rstrip()
            closes_first = head.startswith("}")
            if closes_first:
                depth -= 1
                if rblocks and rblocks[-1]:
                    rblocks.pop()
                else:
                    # a python literal's braces: leave the line untouched
                    out.append(indent + stripped + suffix)
                    depth += 1
                    continue
                head = head[1:].strip()
                indent = "    " * depth
            kw = (
                head.split("(", 1)[0].strip()
                if "(" in head
                else (head.split()[0] if head.split() else "")
            )
            if kw in ("if", "while", "for"):
                inside = _balanced_paren(head[len(kw) :])
                if inside is None or not inside.strip():
                    raise TransformError(
                        f"cannot parse R block header {head!r}: the condition must "
                        "close on the same line as '{'"
                    )
                if kw == "for":
                    parts = _split_for_tokens(inside)
                    if not parts:
                        raise TransformError(f"cannot parse for-loop header {head!r}")
                    new_code = f"for {parts[0]} in {parts[1]}:"
                else:
                    new_code = f"{kw} {inside.strip()}:"
            elif head == "repeat":
                new_code = "while True:"
            elif head.startswith("else"):
                tail = head[4:].strip()
                if tail.startswith("if "):
                    inside = _balanced_paren(tail[2:])
                    if inside is None or not inside.strip():
                        raise TransformError(f"cannot parse 'else if' header {head!r}")
                    new_code = f"elif {inside.strip()}:"
                elif not tail:
                    new_code = "else:"
                else:
                    raise TransformError(f"cannot parse R block header {head!r}")
            elif "function" in head.split("(")[0]:
                raise TransformError("R 'function(...) {...}' is not supported; use a Python def()")
            else:
                out.append(indent + stripped + suffix)
                depth += 1
                rblocks.append(False)
                continue
            out.append(indent + new_code + suffix)
            depth += 1
            rblocks.append(True)
            continue
        out.append(line if depth == 0 else indent + stripped + suffix)
    if rblocks:
        raise TransformError("unbalanced R blocks: '{' without a closing '}'")
    return "\n".join(out)


def _autoprint(src: str) -> str:
    """Echo top-level expression results the way the R console does."""
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        raise TransformError(f"syntax error in transformed source: {exc.msg}") from None
    silent = {"cat", "print", "exit", "quit", "plot", "hist", "barplot"}
    echo = ast.Attribute(value=ast.Name(id="PyRlang", ctx=ast.Load()), attr="_echo", ctx=ast.Load())
    changed = False
    for stmt in tree.body:
        if not isinstance(stmt, ast.Expr):
            continue
        val = stmt.value
        if isinstance(val, ast.Constant) and isinstance(val.value, str) and stmt is tree.body[0]:
            continue  # module docstring
        if isinstance(val, ast.Call):
            fn = val.func
            name = fn.id if isinstance(fn, ast.Name) else None
            if name in silent:
                continue
        call = ast.Call(func=ast.copy_location(echo, val), args=[val], keywords=[])
        ast.copy_location(call, val)
        stmt.value = call
        changed = True
    if not changed:
        return src
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def transform(source: str, autoprint: bool = False) -> str:
    """Rewrite R-flavoured source into pure Python (see module docstring)."""
    src = _prepass_dollar(source)
    src = _convert_blocks(src)
    for _ in range(2000):
        scan = _Scan(src)
        edit = _find_edit(scan)
        if edit is None:
            break
        start, end, replacement = edit
        src = src[:start] + replacement + src[end:]
    else:
        raise TransformError("transform did not converge")
    if autoprint:
        src = _autoprint(src)
    return src
