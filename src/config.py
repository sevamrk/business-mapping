"""Settings, read from the environment every time they are asked for.

Read at call time rather than at import, so a test can change one without
reloading the module and a long-running process picks up a change on the next
call. There are no credentials here and nothing to obtain: a fresh clone runs
with an empty environment.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MAP = "examples/harbourgate-coffee.json"


def map_path() -> Path:
    """The map to read. Relative paths resolve against the repository root."""
    raw = os.environ.get("FUNCTION_MAP_PATH", "").strip() or DEFAULT_MAP
    path = Path(raw).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


def hours_per_fte_year() -> float:
    """Working hours behind one full-time person, for turning hours into headcount.

    1600 is a European year after holiday and sick leave. It is a blunt number
    and it is here as a setting because arguing about it is more productive
    than hiding it in a formula.
    """
    return _positive_float("HOURS_PER_FTE_YEAR", 1600.0)


def rank_limit() -> int:
    """How many rows ``rank`` prints before it stops. 0 means all of them."""
    raw = os.environ.get("RANK_LIMIT", "").strip()
    if not raw:
        return 15
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"RANK_LIMIT must be a whole number, found '{raw}'") from exc
    if value < 0:
        raise ConfigError("RANK_LIMIT must not be negative")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, found '{raw}'") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be greater than zero")
    return value


class ConfigError(ValueError):
    """A setting was present and unusable, which is different from absent."""
