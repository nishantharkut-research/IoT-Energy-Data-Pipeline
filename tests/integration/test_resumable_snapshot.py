from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from iot_energy_pipeline.canonicalize import build_snapshot
from iot_energy_pipeline.resumable_snapshot import build_resumable_snapshot
from tests.integration.test_canonical_snapshot import _rules, _source, _xml_source


def test_resumable_snapshot_matches_legacy_bytes(tmp_path: Path) -> None:
    manifest = _source(tmp_path)
    expected = build_snapshot(manifest, tmp_path / "legacy", _rules())
    actual = build_resumable_snapshot(
        manifest,
        tmp_path / "new",
        _rules(),
        workspace=tmp_path / "work",
        buffer_bytes=100,
        merge_fan_in=2,
    )
    for name in (
        "canonical.ndjson",
        "canonical.parquet",
        "source-quality.ndjson",
        "snapshot-manifest.json",
    ):
        assert (tmp_path / "legacy" / name).read_bytes() == (
            tmp_path / "new" / name
        ).read_bytes()
    assert actual.manifest == expected.manifest


def test_resume_skips_committed_workbooks(tmp_path: Path, monkeypatch) -> None:
    import iot_energy_pipeline.resumable_snapshot as module

    manifest = _source(tmp_path)

    def interrupt(progress):
        if progress["phase"] == "workbook_complete":
            raise RuntimeError("interrupted")

    with pytest.raises(RuntimeError, match="interrupted"):
        build_resumable_snapshot(
            manifest,
            tmp_path / "new",
            _rules(),
            workspace=tmp_path / "work",
            progress=interrupt,
        )
    monkeypatch.setattr(
        module, "_canonicalize", lambda *a, **kw: pytest.fail("reprocessed checkpoint")
    )
    result = build_resumable_snapshot(
        manifest, tmp_path / "new", _rules(), workspace=tmp_path / "work"
    )
    assert result.event_count == 3
    assert result.source_quality_count == 2


def test_resume_rejects_changed_rules_and_corrupt_output(tmp_path: Path) -> None:
    manifest = _source(tmp_path)

    def interrupt(progress):
        if progress["phase"] == "workbook_complete":
            raise RuntimeError("interrupted")

    with pytest.raises(RuntimeError):
        build_resumable_snapshot(
            manifest,
            tmp_path / "new",
            _rules(),
            workspace=tmp_path / "work",
            progress=interrupt,
        )
    with pytest.raises(ValueError, match="identity"):
        build_resumable_snapshot(
            manifest,
            tmp_path / "new",
            replace(_rules(), timezone_evidence="changed"),
            workspace=tmp_path / "work",
        )
    checkpoint = next((tmp_path / "work" / "units").glob("*/checkpoint.json"))
    metadata = json.loads(checkpoint.read_text())
    artifact = checkpoint.parent / metadata["artifacts"]["events"]["file"]
    artifact.write_bytes(artifact.read_bytes() + b"{}\n")
    with pytest.raises(ValueError, match="checkpoint"):
        build_resumable_snapshot(
            manifest, tmp_path / "new", _rules(), workspace=tmp_path / "work"
        )


def test_two_workers_produce_same_snapshot(tmp_path: Path) -> None:
    import shutil

    from iot_energy_pipeline.manifests import register_dataset

    manifest = _source(tmp_path)
    for suffix in ("2", "3"):
        shutil.copyfile(
            manifest._root / "readings.xlsx", manifest._root / f"readings{suffix}.xlsx"
        )
    manifest = register_dataset(
        manifest._root,
        tmp_path / "multi-manifest.json",
        dataset_version="fixture-v1",
        source_variant="clean",
    )
    rules = _rules()
    rules = replace(
        rules,
        source_layout=replace(
            rules.source_layout,
            rules=(
                replace(
                    rules.source_layout.rules[0],
                    relative_path_pattern=r"readings\d*\.xlsx",
                ),
            ),
        ),
    )
    build_snapshot(manifest, tmp_path / "legacy", rules)
    build_resumable_snapshot(
        manifest,
        tmp_path / "new",
        rules,
        workspace=tmp_path / "work",
        workers=2,
        merge_fan_in=2,
        buffer_bytes=100,
    )
    assert (tmp_path / "new/snapshot-manifest.json").read_bytes() == (
        tmp_path / "legacy/snapshot-manifest.json"
    ).read_bytes()


@pytest.mark.parametrize("numeric", [str(10**38 - 1), str(-(10**38 - 1))])
def test_resumable_preserves_wide_decimals(tmp_path: Path, numeric: str) -> None:
    from iot_energy_pipeline.canonicalize import MeasurementRule

    manifest = _xml_source(tmp_path, numeric)
    rules = _rules().with_measurement(
        "meter-a", MeasurementRule("cumulative_energy", "kWh", 0, "fixture")
    )
    build_snapshot(manifest, tmp_path / "legacy", rules)
    build_resumable_snapshot(
        manifest, tmp_path / "new", rules, workspace=tmp_path / "work"
    )
    for name in ("canonical.ndjson", "canonical.parquet", "source-quality.ndjson"):
        assert (tmp_path / "legacy" / name).read_bytes() == (
            tmp_path / "new" / name
        ).read_bytes()


def test_resume_restarts_partial_export(tmp_path: Path) -> None:
    manifest = _source(tmp_path)

    def interrupt(progress):
        if progress["phase"] == "writing_parquet":
            raise RuntimeError("export interrupted")

    with pytest.raises(RuntimeError, match="export interrupted"):
        build_resumable_snapshot(
            manifest,
            tmp_path / "new",
            _rules(),
            workspace=tmp_path / "work",
            progress=interrupt,
        )
    assert (tmp_path / "work/export/canonical.ndjson").exists()
    result = build_resumable_snapshot(
        manifest, tmp_path / "new", _rules(), workspace=tmp_path / "work"
    )
    assert result.event_count == 3


def test_merge_rejects_duplicate_sources_across_runs(tmp_path: Path) -> None:
    from iot_energy_pipeline.resumable_snapshot import _merge

    for name in ("a", "b"):
        (tmp_path / name).write_text('{"source_event_id":"same"}\n')
    with pytest.raises(ValueError, match="duplicate"):
        _merge([tmp_path / "a", tmp_path / "b"], tmp_path / "output", quality=False)


def test_empty_snapshot_matches_legacy(tmp_path: Path) -> None:
    manifest = _source(tmp_path)
    manifest = replace(
        manifest, files=tuple(f for f in manifest.files if f.media_kind == "brick_ttl")
    )
    build_snapshot(manifest, tmp_path / "legacy", _rules())
    build_resumable_snapshot(
        manifest, tmp_path / "new", _rules(), workspace=tmp_path / "work"
    )
    assert (tmp_path / "legacy/snapshot-manifest.json").read_bytes() == (
        tmp_path / "new/snapshot-manifest.json"
    ).read_bytes()


def test_workspace_rejects_second_writer(tmp_path: Path) -> None:
    from iot_energy_pipeline.resumable_snapshot import _lock

    with _lock(tmp_path / "lock"), pytest.raises(OSError):
        with _lock(tmp_path / "lock"):
            pytest.fail("second writer acquired lock")


def test_resume_waits_for_surviving_worker_lease(tmp_path: Path, monkeypatch) -> None:
    import hashlib
    import subprocess
    import sys
    from contextlib import contextmanager

    import iot_energy_pipeline.resumable_snapshot as module

    manifest = _source(tmp_path)
    units = tmp_path / "work/units"
    units.mkdir(parents=True)
    name = hashlib.sha256(b"readings.xlsx").hexdigest()
    partial = units / f".{name}.surviving"
    partial.mkdir()
    marker = partial / "active"
    marker.write_text("worker is using this directory")
    attempted = tmp_path / "lease-attempted"
    original_lock = module._lock

    @contextmanager
    def observed_lock(path, wait_seconds=0):
        if path.name == f"{name}.lock":
            attempted.write_text("replacement is acquiring the lease")
        with original_lock(path, wait_seconds):
            yield

    monkeypatch.setattr(module, "_lock", observed_lock)
    script = (
        "from pathlib import Path; import sys,time; "
        "from iot_energy_pipeline.resumable_snapshot import _lock; "
        "\nwith _lock(Path(sys.argv[1])):"
        "\n print('ready',flush=True)"
        "\n deadline=time.monotonic()+10"
        "\n while not Path(sys.argv[3]).exists():"
        "\n  assert time.monotonic()<deadline, 'replacement never attempted lease'"
        "\n  time.sleep(0.01)"
        "\n assert Path(sys.argv[2]).exists(), 'active workspace was removed'"
    )
    with subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            str(units / f"{name}.lock"),
            str(marker),
            str(attempted),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as holder:
        assert holder.stdout.readline().strip() == "ready"
        result = build_resumable_snapshot(
            manifest, tmp_path / "new", _rules(), workspace=tmp_path / "work"
        )
        _, errors = holder.communicate(timeout=10)
        assert holder.returncode == 0, errors
        assert result.event_count == 3
    assert not partial.exists()
