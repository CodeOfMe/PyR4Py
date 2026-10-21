"""R's formula objects: ``y ~ x`` stored as data, ready for future modelling."""

from __future__ import annotations

__all__ = ["Formula"]


class Formula:
    """A lightweight R formula: ``Formula("y ~ x")``.

    In ``.pyr`` files and the REPL you write bare R syntax::

        f = wage ~ age + education

    which the PyRlang transformer rewrites to ``Formula('wage ~ age + education')``.

    The left/right sides are parsed shallowly so you can inspect a model
    description; no statistical engine is attached in PyRlang 0.1.
    """

    __slots__ = ("text", "_lhs", "_rhs")

    def __init__(self, text: str):
        if not isinstance(text, str):
            raise TypeError("Formula() expects a string like 'y ~ x'")
        cleaned = " ".join(text.split())
        if "~" not in cleaned:
            raise ValueError(f"not a formula (no '~' found): {text!r}")
        self.text = cleaned
        left, right = cleaned.split("~", 1)
        self._lhs = left.strip()
        self._rhs = right.strip()

    @property
    def lhs(self) -> str:
        """Left-hand side variables (response), '' for one-sided formulas."""
        return self._lhs

    @property
    def rhs(self) -> str:
        """Right-hand side terms."""
        return self._rhs

    @property
    def terms(self) -> list[str]:
        """Right-hand side terms split on '+' (a shallow parse)."""
        if not self._rhs:
            return []
        return [t.strip() for t in self._rhs.split("+")]

    def __repr__(self) -> str:
        return self.text

    def __str__(self) -> str:
        return self.text

    def __eq__(self, other):
        if isinstance(other, Formula):
            return self.text == other.text
        if isinstance(other, str):
            return self.text == " ".join(other.split())
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.text)
