"""Write an evaluation's winner back into the env files, so it reaches the running application."""

from pathlib import Path

_ROOT = Path(__file__).parent.parent

ENV_FILES = (_ROOT / ".env", _ROOT / ".env.example")


def _find_line(path: Path, key: str) -> tuple[list[str], int]:
    """Return an env file's lines and the index of its `key=` line, raising if it has none."""
    lines = path.read_text().splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            return lines, index
    # Appending instead would leave a duplicate key, so a missing line is worth raising on.
    raise ValueError(f"{path} has no {key} line, so the evaluation's winner would not take effect")


def check_settable(key: str) -> None:
    """Raise before an evaluation spends anything if its winner could not be written afterwards."""
    for path in ENV_FILES:
        _find_line(path, key)


def write_setting(path: Path, key: str, value: str) -> None:
    """Rewrite one env file's `key=` line in place, leaving every other line untouched."""
    lines, index = _find_line(path, key)
    lines[index] = f"{key}={value}\n"
    # Replace atomically: a half-written .env would lose the API keys it also holds.
    temporary = path.parent / f"{path.name}.tmp"
    temporary.write_text("".join(lines))
    temporary.replace(path)
