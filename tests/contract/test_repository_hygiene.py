"""Keep machine-specific LaTeX intermediates outside version control."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("suffix", [".aux", ".fls", ".fdb_latexmk"])
def test_latex_intermediates_are_ignored(tmp_path: Path, suffix: str) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(
        Path(".gitignore").read_text(encoding="utf-8"), encoding="utf-8"
    )
    result = subprocess.run(
        ["git", "check-ignore", f"docs/brief{suffix}"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"LaTeX intermediate is not ignored: {suffix}"


def test_latex_intermediates_are_not_tracked() -> None:
    result = subprocess.run(
        ["git", "ls-files", "-z", "*.aux", "*.fls", "*.fdb_latexmk"],
        capture_output=True,
        check=True,
    )
    assert result.stdout == b"", "Generated LaTeX intermediates must not be tracked"
