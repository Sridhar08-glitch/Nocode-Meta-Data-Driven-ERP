"""Pure semantic-version parsing + constraint matching."""
import pytest

from apps.packaging import semver


@pytest.mark.parametrize("raw,expect", [
    ("1.2.3", (1, 2, 3)), ("v2.0.0", (2, 0, 0)), ("1", (1, 0, 0)), ("1.5", (1, 5, 0)),
    ("10.20.30", (10, 20, 30)), ("1.0.0-rc.1", (1, 0, 0)),
])
def test_parse(raw, expect):
    v = semver.parse(raw)
    assert (v.major, v.minor, v.patch) == expect


def test_invalid_version():
    assert not semver.is_valid("nope")
    assert not semver.is_valid("1.2.3.4.5-bad!")
    with pytest.raises(semver.InvalidVersionError):
        semver.parse("abc")


def test_ordering_and_compare():
    assert semver.compare("1.0.0", "1.0.1") == -1
    assert semver.compare("2.0.0", "1.9.9") == 1
    assert semver.compare("1.2.3", "1.2.3") == 0
    # release outranks its prerelease (semver §11.3)
    assert semver.parse("1.0.0") > semver.parse("1.0.0-rc.1")
    assert semver.parse("1.0.0-alpha") < semver.parse("1.0.0-beta")


@pytest.mark.parametrize("ver,constraint,ok", [
    ("1.2.3", "", True), ("1.2.3", "*", True), ("1.2.3", "any", True),
    ("1.2.3", "1.2.3", True), ("1.2.3", "==1.2.3", True), ("1.2.4", "1.2.3", False),
    ("1.2.3", "!=1.2.3", False), ("1.2.4", "!=1.2.3", True),
    ("1.2.0", ">=1.0.0", True), ("0.9.0", ">=1.0.0", False),
    ("1.5.0", ">1.4.0", True), ("1.5.0", "<2.0.0", True), ("2.0.0", "<2.0.0", False),
    ("1.5.0", ">=1.0.0,<2.0.0", True), ("2.5.0", ">=1.0.0,<2.0.0", False),
    ("1.2.5", "^1.2.0", True), ("1.9.0", "^1.2.0", True), ("2.0.0", "^1.2.0", False),
    ("0.2.5", "^0.2.0", True), ("0.3.0", "^0.2.0", False),   # caret on 0.x pins minor
    ("1.2.9", "~1.2.3", True), ("1.3.0", "~1.2.3", False),
    ("2.5.0", "^1.0.0 || ^2.0.0", True), ("3.0.0", "^1.0.0 || ^2.0.0", False),
])
def test_satisfies(ver, constraint, ok):
    assert semver.satisfies(ver, constraint) is ok


def test_max_version():
    assert semver.max_version(["1.0.0", "2.3.1", "2.3.0", "bad"]) == "2.3.1"
    assert semver.max_version([]) is None
