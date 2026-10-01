"""Reading a map off disk: parse, validate, then build. Never two of those at once."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .model import Actor, Artifact, Automation, Function, FunctionMap
from .validate import Error, validate


class MapError(Exception):
    """The file could not become a map. Carries every reason, not the first."""

    def __init__(self, path, errors) -> None:
        self.path = path
        self.errors = list(errors)
        super().__init__(f"{path}: {len(self.errors)} problem(s)")


def load_text(text: str, path: str = "<string>") -> FunctionMap:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MapError(path, [Error("invalid_json", "$", str(exc))]) from exc
    return build(raw, path)


def load(path) -> FunctionMap:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise MapError(str(path), [Error("missing_file", "$", "no such file")]) from exc
    return load_text(text, str(path))


def digest(raw) -> str:
    """SHA-256 of the map in canonical form, so a report can name the exact map it came from.

    web/src/digest.js computes the same value and the canvas refuses a report whose hash
    is not the map's. Keys sorted, no whitespace, non-ASCII kept, UTF-8, and every number
    written the way JavaScript writes it: json.dumps gives ``1.0``, ``1e-05`` and
    ``1e+16`` where JSON.stringify gives ``1``, ``0.00001`` and ``10000000000000000``.
    """
    return hashlib.sha256(_canonical(raw).encode("utf-8")).hexdigest()


def digest_file(path) -> str:
    return digest(json.loads(Path(path).read_text(encoding="utf-8")))


def _canonical(value) -> str:
    if isinstance(value, dict):
        items = sorted(value.items())
        return "{" + ",".join(f"{_canonical(str(k))}:{_canonical(v)}" for k, v in items) + "}"
    if isinstance(value, list):
        return "[" + ",".join(_canonical(v) for v in value) + "]"
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return _js_number(value)
    raise TypeError(f"not a JSON value: {value!r}")


def _js_number(x) -> str:
    """ECMAScript Number::toString. Python's repr already gives the shortest round-trip
    digits; only where the decimal point goes and when to switch to an exponent differ."""
    if isinstance(x, int):
        x = float(x)  # JavaScript has only doubles: 10**17 reads back as 100000000000000000
    if x != x or x in (float("inf"), float("-inf")):
        raise ValueError("NaN and Infinity are not JSON")
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    mantissa, _, exp = repr(abs(x)).partition("e")
    whole, _, frac = mantissa.partition(".")
    digits = (whole + frac.rstrip("0")).lstrip("0") or "0"
    # value = 0.digits * 10**n, counting the leading zeros lstrip took off a "0.000ddd"
    n = len(whole) + int(exp or 0)
    if whole == "0":
        n = -(len(frac) - len(frac.lstrip("0")))
    digits = digits.rstrip("0") or "0"
    k = len(digits)
    if k <= n <= 21:
        out = digits + "0" * (n - k)
    elif 0 < n <= 21:
        out = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * -n + digits
    else:
        e = n - 1
        point = "." + digits[1:] if k > 1 else ""
        out = f"{digits[0]}{point}e{'+' if e > 0 else '-'}{abs(e)}"
    return sign + out


def build(raw, path: str = "<memory>") -> FunctionMap:
    """Validate first, and only construct once there is nothing left to report."""
    errors = validate(raw)
    if errors:
        raise MapError(path, errors)

    actors = tuple(
        Actor(a["id"], a["name"], a["kind"], a.get("notes", "")) for a in raw["actors"]
    )
    artifacts = tuple(
        Artifact(a["id"], a["name"], a["form"], a["boundary"], a.get("notes", ""))
        for a in raw["artifacts"]
    )
    functions = tuple(
        Function(
            id=f["id"],
            name=f["name"],
            area=f["area"],
            description=f["description"],
            owner=f["owner"],
            performers=tuple(f["performers"]),
            trigger=f["trigger"],
            inputs=tuple(f["inputs"]),
            outputs=tuple(f["outputs"]),
            volume_per_month=float(f["volume_per_month"]),
            minutes_per_run=float(f["minutes_per_run"]),
            current_state=f["current_state"],
            automation=Automation.from_dict(f["automation"]),
            notes=f.get("notes", ""),
        )
        for f in raw["functions"]
    )
    return FunctionMap(
        company=raw["company"],
        description=raw["description"],
        actors=actors,
        artifacts=artifacts,
        functions=functions,
    )
