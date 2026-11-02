"""Bounded external sorting with verified, reusable workbook outputs."""

from __future__ import annotations

import hashlib
import heapq
import importlib
import json
import os
import shutil
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterator, cast

from .brick import load_brick_metadata
from .canonicalize import (
    CanonicalizationRules,
    SnapshotResult,
    _canonical_json_bytes,
    _canonicalize,
    _manifest_projection,
    _parquet_modules_and_schema,
    _registered_brick_path,
    _sha256,
    _snapshot_manifest,
)
from .manifests import DatasetManifest, FileManifest

_STATE: tuple[Any, ...] = ()


@contextmanager
def _lock(path: Path, wait_seconds: float = 0) -> Iterator[None]:
    # OS-owned locks release on process exit, including abnormal termination.
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl = importlib.import_module("fcntl")

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _sync(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _key(line: bytes, quality: bool) -> Any:
    row = json.loads(line)
    if quality:
        return (
            row["source_relative_path"],
            row["workbook_sheet"],
            row["source_row_number"],
            row["category"],
        )
    return row["source_event_id"]


def _merge(
    paths: list[Path],
    output: Path,
    *,
    quality: bool,
    notify: Callable[[int, str], None] | None = None,
) -> int:
    """Merge already ordered runs, rejecting duplicate identities."""
    count = 0
    previous: Any = None
    with ExitStack() as stack:
        streams = [stack.enter_context(p.open("rb")) for p in paths]
        destination = stack.enter_context(output.open("xb"))
        for line in heapq.merge(*streams, key=lambda b: _key(b, quality)):
            key = _key(line, quality)
            if previous is not None and key <= previous:
                raise ValueError("duplicate or unordered source identity during merge")
            destination.write(line)
            previous = key
            count += 1
            if notify and count % 100_000 == 0:
                notify(count, output.name)
        destination.flush()
        os.fsync(destination.fileno())
    return count


def _merge_bounded(
    paths: list[Path],
    output: Path,
    stage: Path,
    quality: bool,
    fan_in: int,
    notify: Callable[[int, str], None] | None = None,
) -> int:
    current = paths
    generation = 0
    while len(current) > fan_in:
        following = []
        for offset in range(0, len(current), fan_in):
            merged = stage / f"merge-{output.stem}-{generation}-{offset}.ndjson"
            _merge(
                current[offset : offset + fan_in],
                merged,
                quality=quality,
                notify=notify,
            )
            following.append(merged)
        # Only disposable merge outputs owned by this stage may be removed.
        if generation:
            for path in current:
                path.unlink()
        current = following
        generation += 1
    count = _merge(current, output, quality=quality, notify=notify)
    if generation:
        for path in current:
            path.unlink()
    return count


class _Runs:
    def __init__(self, stage: Path, name: str, budget: int) -> None:
        self.stage, self.name, self.budget = stage, name, budget
        self.buffer: list[bytes] = []
        self.size = 0
        self.paths: list[Path] = []

    def add(self, row: dict[str, Any]) -> None:
        line = _canonical_json_bytes(row)
        self.buffer.append(line)
        self.size += len(line)
        if self.size >= self.budget:
            self.flush()

    def flush(self) -> None:
        if not self.buffer:
            return
        self.buffer.sort(key=lambda b: _key(b, self.name == "quality"))
        path = self.stage / f"{self.name}-run-{len(self.paths)}.ndjson"
        with path.open("xb") as stream:
            stream.writelines(self.buffer)
        self.paths.append(path)
        self.buffer.clear()
        self.size = 0

    def finish(self, fan_in: int) -> tuple[Path, int]:
        self.flush()
        output = self.stage / f"{self.name}.ndjson"
        count = _merge_bounded(
            self.paths, output, self.stage, self.name == "quality", fan_in
        )
        for path in self.paths:
            path.unlink()
        return output, count


def _initialize(
    manifest: DatasetManifest,
    rule_args: dict[str, Any],
    units: Path,
    budget: int,
    fan_in: int,
    min_free: int,
) -> None:
    global _STATE
    rules = CanonicalizationRules(**rule_args)
    brick = load_brick_metadata(_registered_brick_path(manifest))
    _STATE = manifest, rules, brick, units, budget, fan_in, min_free


def _prepare_unit(file: FileManifest) -> dict[str, Any]:
    units = _STATE[3]
    name = hashlib.sha256(file.relative_path.encode()).hexdigest()
    with _lock(units / f"{name}.lock", wait_seconds=600):
        target = units / name
        if target.exists():
            return _verify_unit(target, file)
        for partial in units.glob(f".{name}.*"):
            if partial.is_symlink() or not partial.resolve().is_relative_to(
                units.resolve()
            ):
                raise ValueError("unsafe partial checkpoint directory")
            shutil.rmtree(partial)
        return _prepare_unit_locked(file)


def _prepare_unit_locked(file: FileManifest) -> dict[str, Any]:
    manifest, rules, brick, units, budget, fan_in, min_free = _STATE
    if shutil.disk_usage(units).free < min_free:
        raise RuntimeError("Insufficient disk headroom for preparation")
    started = time.perf_counter()
    name = hashlib.sha256(file.relative_path.encode()).hexdigest()
    target = units / name
    stage = Path(tempfile.mkdtemp(prefix=f".{name}.", dir=units))
    selected = tuple(
        f for f in manifest.files if f.media_kind == "brick_ttl" or f == file
    )
    subset = DatasetManifest(
        manifest.dataset_version, manifest.source_variant, selected, manifest._root
    )
    events = _Runs(stage, "events", budget)
    quality = _Runs(stage, "quality", budget)
    _canonicalize(
        subset,
        rules,
        event_sink=events.add,
        quality_sink=quality.add,
        brick_metadata=brick,
    )
    artifacts: dict[str, Any] = {}
    for label, runs in (("events", events), ("quality", quality)):
        path, count = runs.finish(fan_in)
        artifacts[label] = {
            "file": path.name,
            "record_count": count,
            "byte_size": path.stat().st_size,
            "sha256": _sha256(path),
        }
    checkpoint = {
        "source": asdict(file),
        "artifacts": artifacts,
        "physical_rows": sum(a["record_count"] for a in artifacts.values()),
        "seconds": time.perf_counter() - started,
    }
    _sync(stage / "checkpoint.json", _canonical_json_bytes(checkpoint, pretty=True))
    stage.rename(target)
    return checkpoint


def _verify_unit(path: Path, file: FileManifest) -> dict[str, Any]:
    try:
        value = json.loads((path / "checkpoint.json").read_bytes())
        if value["source"] != asdict(file):
            raise ValueError("source mismatch")
        for label in ("events", "quality"):
            item = value["artifacts"][label]
            if item["file"] != f"{label}.ndjson":
                raise ValueError("unexpected output name")
            artifact = path / item["file"]
            if artifact.is_symlink() or artifact.stat().st_size != item["byte_size"]:
                raise ValueError("output size mismatch")
            if _sha256(artifact) != item["sha256"]:
                raise ValueError("output hash mismatch")
        if value["physical_rows"] != sum(
            a["record_count"] for a in value["artifacts"].values()
        ):
            raise ValueError("count mismatch")
        return cast(dict[str, Any], value)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(f"Invalid preparation checkpoint: {path}") from error


def _write_parquet(
    ndjson: Path, output: Path, notify: Callable[[int], None] | None = None
) -> tuple[int, set[str]]:
    pa, pq, schema = _parquet_modules_and_schema()
    count = 0
    unmatched: set[str] = set()
    with pq.ParquetWriter(
        output,
        schema,
        compression="zstd",
        use_dictionary=False,
        write_statistics=True,
        version="2.6",
    ) as writer:
        batch = []
        with ndjson.open("rb") as source:
            for line in source:
                row = json.loads(line)
                if row["brick_entity_id"] is None:
                    unmatched.add(row["meter_id"])
                row["scaled_value"] = Decimal(row["scaled_value"])
                batch.append(row)
                count += 1
                if notify and count % 100_000 == 0:
                    notify(count)
                if len(batch) == 10_000:
                    writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                    batch.clear()
        if batch or not count:
            writer.write_table(pa.Table.from_pylist(batch, schema=schema))
    with output.open("r+b") as stream:
        stream.flush()
        os.fsync(stream.fileno())
    return count, unmatched


def build_resumable_snapshot(
    manifest: DatasetManifest,
    output_dir: Path,
    rules: CanonicalizationRules,
    *,
    workspace: Path,
    workers: int = 1,
    buffer_bytes: int = 16 * 1024 * 1024,
    merge_fan_in: int = 32,
    min_free_bytes: int = 0,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> SnapshotResult:
    """Publish the existing snapshot format from verified workbook checkpoints.

    An interrupted export restarts from completed units, without rereading XLSX.
    Partial units are never reused. The workspace remains after publication.
    """
    if workers < 1 or workers > 4 or buffer_bytes < 1 or merge_fan_in < 2:
        raise ValueError("Invalid bounded preparation configuration")
    if manifest._root is None:
        raise ValueError("manifest must retain a verified source root")
    if output_dir.exists():
        raise FileExistsError(f"immutable snapshot already exists: {output_dir}")
    workspace = workspace.resolve()
    output_dir = output_dir.resolve()
    if workspace.is_relative_to(output_dir) or output_dir.is_relative_to(workspace):
        raise ValueError("workspace and snapshot must not overlap")
    if workspace.anchor != output_dir.anchor:
        raise ValueError("workspace and snapshot must share a filesystem")
    workspace.mkdir(parents=True, exist_ok=True)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with _lock(workspace / "writer.lock"):
        manifest._validate_files(manifest._root)
        rule_args = {
            "source_timezone": rules.source_timezone,
            "timezone_evidence": rules.timezone_evidence,
            "source_layout": rules.source_layout,
            "measurements": dict(rules.measurements),
        }
        identity = {
            "format": "resumable-preparation-v1",
            "source": _manifest_projection(manifest),
            "rules": {
                "timezone": rules.source_timezone,
                "evidence": rules.timezone_evidence,
                "layout": rules.source_layout.to_dict(),
                "measurements": {
                    k: asdict(v) for k, v in sorted(rules.measurements.items())
                },
            },
            "implementation": {
                p.name: _sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))
            },
        }
        identity_path = workspace / "identity.json"
        identity_bytes = _canonical_json_bytes(identity, pretty=True)
        if identity_path.exists():
            if identity_path.read_bytes() != identity_bytes:
                raise ValueError("preparation identity changed; use a new workspace")
        else:
            temporary = workspace / "identity.pending"
            if temporary.exists():
                temporary.unlink()
            _sync(temporary, identity_bytes)
            temporary.rename(identity_path)
        units = workspace / "units"
        units.mkdir(exist_ok=True)
        files = [f for f in manifest.files if f.media_kind == "workbook"]
        names = [hashlib.sha256(f.relative_path.encode()).hexdigest() for f in files]
        if len(set(names)) != len(names):
            raise ValueError("duplicate workbook source identity")
        if any(
            p.is_dir() and not p.name.startswith(".") and p.name not in names
            for p in units.iterdir()
        ):
            raise ValueError("unexpected preparation checkpoint")
        completed = []
        pending = []
        for file, name in zip(files, names, strict=True):
            if (units / name).exists():
                completed.append(_verify_unit(units / name, file))
            else:
                pending.append(file)

        def report(phase: str, **extra: Any) -> None:
            if progress:
                progress(
                    dict(
                        phase=phase,
                        completed_workbooks=len(completed),
                        total_workbooks=len(files),
                        completed_physical_rows=sum(
                            c["physical_rows"] for c in completed
                        ),
                        **extra,
                    )
                )

        report("preparation_resume", reused_workbooks=len(completed))
        args = (manifest, rule_args, units, buffer_bytes, merge_fan_in, min_free_bytes)
        if workers == 1:
            _initialize(*args)
            for file in pending:
                completed.append(_prepare_unit(file))
                report("workbook_complete", source=file.relative_path)
        else:
            with ProcessPoolExecutor(
                max_workers=workers, initializer=_initialize, initargs=args
            ) as pool:
                remaining = iter(pending)
                futures = {
                    pool.submit(_prepare_unit, file)
                    for file in [next(remaining, None) for _ in range(workers)]
                    if file is not None
                }
                try:
                    while futures:
                        future = next(as_completed(futures))
                        futures.remove(future)
                        checkpoint = future.result()
                        completed.append(checkpoint)
                        report(
                            "workbook_complete",
                            source=checkpoint["source"]["relative_path"],
                        )
                        following = next(remaining, None)
                        if following is not None:
                            futures.add(pool.submit(_prepare_unit, following))
                except BaseException:
                    for future in futures:
                        future.cancel()
                    raise
        report("merging_canonical")
        stage = workspace / "export"
        if stage.exists():
            if stage.is_symlink() or not stage.resolve().is_relative_to(workspace):
                raise ValueError("unsafe partial export directory")
            shutil.rmtree(stage)
        stage.mkdir()
        expected_bytes = sum(
            artifact["byte_size"]
            for checkpoint in completed
            for artifact in checkpoint["artifacts"].values()
        )
        if shutil.disk_usage(workspace).free < 2 * expected_bytes + min_free_bytes:
            raise RuntimeError("Insufficient disk headroom for merge and export")
        event_count = _merge_bounded(
            [units / n / "events.ndjson" for n in names],
            stage / "canonical.ndjson",
            stage,
            False,
            merge_fan_in,
            lambda count, name: report(
                "merging_canonical", processed_rows=count, merge_output=name
            ),
        )
        report("merging_source_quality")
        quality_count = _merge_bounded(
            [units / n / "quality.ndjson" for n in names],
            stage / "source-quality.ndjson",
            stage,
            True,
            merge_fan_in,
            lambda count, name: report(
                "merging_source_quality", processed_rows=count, merge_output=name
            ),
        )
        if event_count != sum(
            c["artifacts"]["events"]["record_count"] for c in completed
        ):
            raise ValueError("merged event counts do not reconcile")
        if quality_count != sum(
            c["artifacts"]["quality"]["record_count"] for c in completed
        ):
            raise ValueError("merged quality counts do not reconcile")
        report("writing_parquet")
        parquet_count, unmatched = _write_parquet(
            stage / "canonical.ndjson",
            stage / "canonical.parquet",
            lambda count: report("writing_parquet", processed_rows=count),
        )
        if parquet_count != event_count:
            raise ValueError("Parquet count does not reconcile")
        report("hashing_snapshot")
        brick = load_brick_metadata(_registered_brick_path(manifest))
        snapshot = _snapshot_manifest(
            manifest, rules, brick, unmatched, stage, event_count, quality_count
        )
        _sync(
            stage / "snapshot-manifest.json",
            _canonical_json_bytes(snapshot, pretty=True),
        )
        stage.rename(output_dir)
        report("snapshot_complete", output=str(output_dir))
        return SnapshotResult(None, None, snapshot)
