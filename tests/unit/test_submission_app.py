"""Portable mode works without runtime files; strict mode rejects missing files."""

from pathlib import Path

import pytest

pytest.importorskip("plotly")
testing = pytest.importorskip("streamlit.testing.v1")

from dashboard.submission import PAGES  # noqa: E402

APP_PATH = Path(__file__).resolve().parents[2] / "dashboard/app.py"


def test_all_portable_views_render_without_runtime_files() -> None:
    app = testing.AppTest.from_file(APP_PATH, default_timeout=15).run()
    assert not app.exception
    for name in PAGES:
        app.sidebar.radio[0].set_value(name).run()
        assert not app.exception
        assert app.title[0].value == name


def test_explicit_sealed_mode_rejects_missing_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IOT_ENERGY_RUN_DIR", str(tmp_path / "absent-run"))
    app = testing.AppTest.from_file(APP_PATH, default_timeout=15).run()
    app.sidebar.selectbox[0].set_value("Sealed run files").run()
    assert not app.exception
    assert "integrity seal is missing" in app.error[0].value
