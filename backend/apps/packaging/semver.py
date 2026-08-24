"""
Semantic-version parsing + constraint matching for the Solution Package Platform.

Pure standard-library (no external dependency) so it is deterministic and identical on
SQLite and PostgreSQL. Versions follow ``MAJOR.MINOR.PATCH`` with an optional
``-prerelease`` and ``+build`` suffix (build metadata is ignored for ordering, per semver).

A *constraint* is a string the way npm/pip authors write them, supporting:

  ``""`` / ``"*"`` / ``"any"``    → matches anything
  ``"1.2.3"`` / ``"==1.2.3"``     → exact
  ``">=1.2.0"`` ``">"`` ``"<"`` ``"<="`` ``"!="``
  ``"^1.2.3"``                    → compatible-with (>=1.2.3,<2.0.0; ^0.2.3 → >=0.2.3,<0.3.0)
  ``"~1.2.3"``                    → approximately (>=1.2.3,<1.3.0)
  comma / space separated         → AND   (e.g. ``">=1.2.0,<2.0.0"``)
  ``"||"`` separated              → OR    (e.g. ``"^1.0.0 || ^2.0.0"``)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_CORE_RE = re.compile(
    r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?\s*$")
_OP_RE = re.compile(r"^\s*(>=|<=|==|!=|>|<|\^|~|=)?\s*(.+?)\s*$")


class InvalidVersionError(ValueError):
    """Raised when a version string cannot be parsed."""


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: tuple = field(default_factory=tuple)

    # ── ordering ──────────────────────────────────────────────────────────────
    def _key(self):
        # A release outranks any prerelease of the same core (semver §11.3): model that
        # by giving releases an empty prerelease that sorts AFTER any non-empty one.
        return (self.major, self.minor, self.patch)

    def __lt__(self, other: Version) -> bool:
        if self._key() != other._key():
            return self._key() < other._key()
        return _pre_lt(self.prerelease, other.prerelease)

    def __le__(self, other: Version) -> bool:
        return self == other or self < other

    def __gt__(self, other: Version) -> bool:
        return other < self

    def __ge__(self, other: Version) -> bool:
        return self == other or other < self

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return f"{base}-{'.'.join(map(str, self.prerelease))}" if self.prerelease else base


def _pre_lt(a: tuple, b: tuple) -> bool:
    """Prerelease ordering: an empty tuple (a release) is HIGHEST."""
    if a == b:
        return False
    if not a:          # release > any prerelease
        return False
    if not b:
        return True
    for x, y in zip(a, b, strict=False):
        if x == y:
            continue
        xi, yi = isinstance(x, int), isinstance(y, int)
        if xi and yi:
            return x < y
        if xi != yi:        # numeric identifiers are lower than alphanumeric
            return xi
        return str(x) < str(y)
    return len(a) < len(b)


def parse(version: str) -> Version:
    if isinstance(version, Version):
        return version
    if not isinstance(version, str):
        raise InvalidVersionError(f"version must be a string, got {type(version).__name__}")
    m = _CORE_RE.match(version)
    if not m:
        raise InvalidVersionError(f"invalid version: {version!r}")
    major = int(m.group(1))
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    pre_raw = m.group(4)
    pre: tuple = ()
    if pre_raw:
        parts = []
        for p in pre_raw.split("."):
            parts.append(int(p) if p.isdigit() else p)
        pre = tuple(parts)
    return Version(major, minor, patch, pre)


def is_valid(version: str) -> bool:
    try:
        parse(version)
        return True
    except InvalidVersionError:
        return False


# ── constraint matching ──────────────────────────────────────────────────────
def _match_single(ver: Version, clause: str) -> bool:
    clause = clause.strip()
    if clause in ("", "*", "any", "x", "X"):
        return True
    m = _OP_RE.match(clause)
    if not m:
        raise InvalidVersionError(f"invalid version constraint clause: {clause!r}")
    op, rest = m.group(1), m.group(2)
    target = parse(rest)
    if op in (None, "=", "=="):
        return ver == target
    if op == "!=":
        return ver != target
    if op == ">":
        return ver > target
    if op == ">=":
        return ver >= target
    if op == "<":
        return ver < target
    if op == "<=":
        return ver <= target
    if op == "^":
        return _caret(ver, target)
    if op == "~":
        return _tilde(ver, target)
    raise InvalidVersionError(f"unsupported operator {op!r}")


def _caret(ver: Version, t: Version) -> bool:
    if ver < t:
        return False
    if t.major > 0:
        upper = Version(t.major + 1, 0, 0)
    elif t.minor > 0:
        upper = Version(0, t.minor + 1, 0)
    else:
        upper = Version(0, 0, t.patch + 1)
    return ver < upper


def _tilde(ver: Version, t: Version) -> bool:
    if ver < t:
        return False
    upper = Version(t.major, t.minor + 1, 0)
    return ver < upper


def satisfies(version: str, constraint: str) -> bool:
    """True if ``version`` satisfies ``constraint`` (see module docstring for the grammar)."""
    if constraint is None:
        return True
    ver = parse(version)
    constraint = str(constraint).strip()
    if constraint in ("", "*", "any"):
        return True
    for or_group in constraint.split("||"):
        clauses = [c for c in re.split(r"[,\s]+", or_group.strip()) if c]
        if not clauses:
            return True
        if all(_match_single(ver, c) for c in clauses):
            return True
    return False


def compare(a: str, b: str) -> int:
    """-1 / 0 / 1 for a<b / a==b / a>b."""
    va, vb = parse(a), parse(b)
    if va == vb:
        return 0
    return -1 if va < vb else 1


def max_version(versions) -> str | None:
    parsed = [(parse(v), v) for v in versions if is_valid(v)]
    if not parsed:
        return None
    return max(parsed, key=lambda pv: pv[0])[1]
