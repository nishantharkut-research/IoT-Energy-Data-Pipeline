"""Unit tests for dataset manifest registration."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from typing import Any

# These imports will fail until implementation exists
from iot_energy_pipeline.manifests import (
    DatasetManifest,
    FileManifest,
    register_dataset,
)


@pytest.fixture(params=["manifest", "profile"])
def immutable_json_writer(request: pytest.FixtureRequest) -> tuple[Any, Any]:
    """Exercise both public serializers through their real filesystem writes."""
    if request.param == "manifest":
        from iot_energy_pipeline import manifests as module

        return DatasetManifest("v1", "raw", ()), module
    from iot_energy_pipeline import profile as module

    return module.DatasetProfile("v1", "raw", ()), module


@pytest.mark.skipif(os.name != "nt", reason="requires Windows no-replace rename")
def test_windows_publication_needs_no_hard_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    immutable_json_writer: tuple[Any, Any],
) -> None:
    writer, module = immutable_json_writer
    writer_os = SimpleNamespace(**vars(os))

    def unsupported_link(*args: Any, **kwargs: Any) -> None:
        raise OSError("hard links unsupported")

    writer_os.link = unsupported_link
    monkeypatch.setattr(module, "os", writer_os)
    output = tmp_path / "output.json"

    writer.to_json(output)

    assert json.loads(output.read_text())["dataset_version"] == "v1"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_posix_publication_cleanup_is_best_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    immutable_json_writer: tuple[Any, Any],
    cleanup_fails: bool,
) -> None:
    writer, module = immutable_json_writer
    writer_os = SimpleNamespace(**vars(os))
    writer_os.name = "posix"
    if cleanup_fails:

        def blocked_cleanup(path: str) -> None:
            raise PermissionError("temporary name is held open")

        writer_os.unlink = blocked_cleanup
    monkeypatch.setattr(module, "os", writer_os)
    output = tmp_path / "output.json"

    writer.to_json(output)

    assert json.loads(output.read_text())["dataset_version"] == "v1"
    temporary = list(tmp_path.glob("output.json.*.tmp"))
    if cleanup_fails:
        assert len(temporary) == 1
        assert temporary[0].read_bytes() == output.read_bytes()
    else:
        assert temporary == []


def test_posix_unsupported_links_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    immutable_json_writer: tuple[Any, Any],
) -> None:
    writer, module = immutable_json_writer
    writer_os = SimpleNamespace(**vars(os))
    writer_os.name = "posix"

    def unsupported_link(*args: Any, **kwargs: Any) -> None:
        raise OSError("hard links unsupported")

    def unsafe_fallback(*args: Any, **kwargs: Any) -> None:
        pytest.fail("unsupported POSIX publication must not fall back to rename")

    writer_os.link = unsupported_link
    writer_os.rename = unsafe_fallback
    writer_os.replace = unsafe_fallback
    monkeypatch.setattr(module, "os", writer_os)

    with pytest.raises(OSError, match="hard links unsupported"):
        writer.to_json(tmp_path / "output.json")

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("platform", ["nt", "posix"])
def test_publication_preserves_competing_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    immutable_json_writer: tuple[Any, Any],
    platform: str,
) -> None:
    if platform == "nt" and os.name != "nt":
        pytest.skip("requires Windows no-replace rename")
    writer, module = immutable_json_writer
    writer_os = SimpleNamespace(**vars(os))
    writer_os.name = platform
    output = tmp_path / "output.json"
    original = b"competing immutable output\n"

    def competing_publication(source: str, destination: Path) -> None:
        output.write_bytes(original)
        if platform == "nt":
            os.rename(source, destination)
        else:
            os.link(source, destination)

    if platform == "nt":
        writer_os.rename = competing_publication
    else:
        writer_os.link = competing_publication
    monkeypatch.setattr(module, "os", writer_os)

    with pytest.raises(FileExistsError):
        writer.to_json(output)

    assert output.read_bytes() == original
    assert list(tmp_path.iterdir()) == [output]


def _make_xlsx(path: Path, content: list[list[Any]] | None = None) -> None:
    """Create a minimal xlsx file using openpyxl."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    if content:
        for row in content:
            ws.append(row)
    wb.save(path)


def _file_sha256(path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.mark.parametrize("path_kind", ["absolute", "windows_parent", "drive_relative"])
def test_loaded_manifest_rejects_paths_outside_source_root(
    tmp_path: Path, path_kind: str
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    outside = tmp_path / "outside.xlsx"
    outside.write_bytes(b"external source boundary probe")
    relative = {
        "absolute": str(outside),
        "windows_parent": "..\\outside.xlsx",
        "drive_relative": "C:outside.xlsx",
    }[path_kind]
    manifest = DatasetManifest(
        "v1",
        "clean",
        (
            FileManifest(
                relative, outside.stat().st_size, _file_sha256(outside), "workbook"
            ),
        ),
    )
    output = tmp_path / "manifest.json"
    manifest.to_json(output)

    with pytest.raises(ValueError, match="unsafe|absolute|escapes"):
        DatasetManifest.from_json(output, root=root)


def test_loaded_manifest_rejects_directory_link_outside_source_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "meter.xlsx"
    target.write_bytes(b"external directory boundary probe")
    try:
        (root / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")
    manifest = DatasetManifest(
        "v1",
        "clean",
        (
            FileManifest(
                "link/meter.xlsx",
                target.stat().st_size,
                _file_sha256(target),
                "workbook",
            ),
        ),
    )
    output = tmp_path / "manifest.json"
    manifest.to_json(output)

    with pytest.raises(ValueError, match="escapes"):
        DatasetManifest.from_json(output, root=root)


class TestFileManifest:
    """Tests for FileManifest dataclass."""

    def test_file_manifest_is_frozen(self, tmp_path: Path) -> None:
        """FileManifest should be immutable (frozen dataclass)."""
        _make_xlsx(tmp_path / "test.xlsx", [[1, 2]])
        manifest = FileManifest(
            relative_path="test.xlsx",
            byte_size=100,
            sha256="abc123",
            media_kind="workbook",
        )
        with pytest.raises(AttributeError):
            manifest.relative_path = "other.xlsx"

    def test_file_manifest_stores_required_fields(self, tmp_path: Path) -> None:
        """FileManifest stores relative_path, byte_size, sha256, media_kind."""
        manifest = FileManifest(
            relative_path="data/test.xlsx",
            byte_size=1024,
            sha256="deadbeef" * 8,
            media_kind="workbook",
        )
        assert manifest.relative_path == "data/test.xlsx"
        assert manifest.byte_size == 1024
        assert manifest.sha256 == "deadbeef" * 8
        assert manifest.media_kind == "workbook"


class TestDatasetManifest:
    """Tests for DatasetManifest dataclass."""

    @pytest.mark.parametrize("created_during_write", [False, True])
    def test_to_json_preserves_existing_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        created_during_write: bool,
    ) -> None:
        output = tmp_path / "manifest.json"
        original = b"existing immutable manifest\r\n"
        manifest = DatasetManifest("v1", "raw", ())
        if created_during_write:
            mkstemp = tempfile.mkstemp

            def create_competing_output(*args: Any, **kwargs: Any) -> tuple[int, str]:
                result = mkstemp(*args, **kwargs)
                output.write_bytes(original)
                return result

            monkeypatch.setattr(tempfile, "mkstemp", create_competing_output)
        else:
            output.write_bytes(original)

        with pytest.raises(FileExistsError):
            manifest.to_json(output)

        assert output.read_bytes() == original
        assert sorted(path.name for path in tmp_path.iterdir()) == [output.name]

    def test_dataset_manifest_is_frozen(self, tmp_path: Path) -> None:
        """DatasetManifest should be immutable."""
        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(),
        )
        with pytest.raises(AttributeError):
            manifest.dataset_version = "v2"

    def test_dataset_manifest_from_json_reloads(self, tmp_path: Path) -> None:
        """DatasetManifest.from_json reconstructs from JSON file."""
        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(
                FileManifest(
                    relative_path="a.xlsx",
                    byte_size=100,
                    sha256="abc",
                    media_kind="workbook",
                ),
            ),
        )
        json_path = tmp_path / "manifest.json"
        manifest.to_json(json_path)

        loaded = DatasetManifest.from_json(json_path)
        assert loaded.dataset_version == "v1"
        assert loaded.source_variant == "raw"
        assert len(loaded.files) == 1
        assert loaded.files[0].relative_path == "a.xlsx"

    def test_dataset_manifest_from_json_validates_files(self, tmp_path: Path) -> None:
        """from_json with root validates files exist and match size/hash."""
        root = tmp_path / "data"
        root.mkdir()
        xlsx_path = root / "test.xlsx"
        _make_xlsx(xlsx_path, [[1, 2]])

        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(
                FileManifest(
                    relative_path="test.xlsx",
                    byte_size=xlsx_path.stat().st_size,
                    sha256=_file_sha256(xlsx_path),
                    media_kind="workbook",
                ),
            ),
        )
        json_path = tmp_path / "manifest.json"
        manifest.to_json(json_path)

        # Should succeed with valid root
        loaded = DatasetManifest.from_json(json_path, root=root)
        assert loaded.dataset_version == "v1"

    def test_dataset_manifest_from_json_rejects_missing_file(
        self, tmp_path: Path
    ) -> None:
        """from_json with root raises error if file is missing."""
        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(
                FileManifest(
                    relative_path="missing.xlsx",
                    byte_size=100,
                    sha256="abc",
                    media_kind="workbook",
                ),
            ),
        )
        json_path = tmp_path / "manifest.json"
        manifest.to_json(json_path)

        root = tmp_path / "data"
        root.mkdir()

        with pytest.raises(ValueError, match="missing.xlsx"):
            DatasetManifest.from_json(json_path, root=root)

    def test_dataset_manifest_from_json_rejects_size_mismatch(
        self, tmp_path: Path
    ) -> None:
        """from_json with root raises error if file size changed."""
        root = tmp_path / "data"
        root.mkdir()
        xlsx_path = root / "test.xlsx"
        _make_xlsx(xlsx_path, [[1, 2]])

        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(
                FileManifest(
                    relative_path="test.xlsx",
                    byte_size=xlsx_path.stat().st_size + 1,  # Wrong size
                    sha256=_file_sha256(xlsx_path),
                    media_kind="workbook",
                ),
            ),
        )
        json_path = tmp_path / "manifest.json"
        manifest.to_json(json_path)

        with pytest.raises(ValueError, match="size"):
            DatasetManifest.from_json(json_path, root=root)

    def test_dataset_manifest_from_json_rejects_hash_mismatch(
        self, tmp_path: Path
    ) -> None:
        """from_json with root raises error if file hash changed."""
        root = tmp_path / "data"
        root.mkdir()
        xlsx_path = root / "test.xlsx"
        _make_xlsx(xlsx_path, [[1, 2]])

        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(
                FileManifest(
                    relative_path="test.xlsx",
                    byte_size=xlsx_path.stat().st_size,
                    sha256="0" * 64,  # Wrong hash
                    media_kind="workbook",
                ),
            ),
        )
        json_path = tmp_path / "manifest.json"
        manifest.to_json(json_path)

        with pytest.raises(ValueError, match="hash"):
            DatasetManifest.from_json(json_path, root=root)


class TestRegisterDataset:
    """Tests for register_dataset function."""

    def test_existing_output_rejected_before_source_scan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "data"
        root.mkdir()
        output = tmp_path / "manifest.json"
        original = b"existing immutable manifest\n"
        output.write_bytes(original)

        def unexpected_scan(root: Path) -> list[Path]:
            pytest.fail("existing output must be rejected before scanning sources")

        monkeypatch.setattr(
            "iot_energy_pipeline.manifests._collect_all_files", unexpected_scan
        )
        with pytest.raises(FileExistsError):
            register_dataset(
                root=root,
                output=output,
                dataset_version="v1",
                source_variant="raw",
            )

        assert output.read_bytes() == original

    def test_register_missing_root_raises(self, tmp_path: Path) -> None:
        """Registering a non-existent root raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            register_dataset(
                root=tmp_path / "missing",
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="raw",
            )

    def test_register_file_root_raises(self, tmp_path: Path) -> None:
        """Registering a file instead of directory raises ValueError."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")
        with pytest.raises(ValueError, match="not a directory"):
            register_dataset(
                root=file_path,
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="raw",
            )

    def test_register_empty_dataset_raises(self, tmp_path: Path) -> None:
        """Registering an empty directory raises ValueError."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(ValueError, match="No files"):
            register_dataset(
                root=empty_dir,
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="raw",
            )

    def test_register_empty_version_raises(self, tmp_path: Path) -> None:
        """Empty dataset_version raises ValueError."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])
        with pytest.raises(ValueError, match="dataset_version"):
            register_dataset(
                root=data_dir,
                output=tmp_path / "manifest.json",
                dataset_version="  ",
                source_variant="raw",
            )

    def test_register_invalid_variant_raises(self, tmp_path: Path) -> None:
        """Invalid source_variant raises ValueError."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])
        with pytest.raises(ValueError, match="source_variant"):
            register_dataset(
                root=data_dir,
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="invalid",
            )

    def test_register_single_xlsx(self, tmp_path: Path) -> None:
        """Register a single xlsx file."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        xlsx_path = data_dir / "test.xlsx"
        _make_xlsx(xlsx_path, [[1, 2], [3, 4]])

        output_path = tmp_path / "manifest.json"
        manifest = register_dataset(
            root=data_dir,
            output=output_path,
            dataset_version="v1",
            source_variant="raw",
        )

        assert manifest.dataset_version == "v1"
        assert manifest.source_variant == "raw"
        assert len(manifest.files) == 1
        assert manifest.files[0].relative_path == "test.xlsx"
        assert manifest.files[0].byte_size == xlsx_path.stat().st_size
        assert manifest.files[0].sha256 == _file_sha256(xlsx_path)
        assert manifest.files[0].media_kind == "workbook"

    def test_register_single_ttl(self, tmp_path: Path) -> None:
        """Register a single ttl file."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        ttl_path = data_dir / "brick.ttl"
        ttl_path.write_text("@prefix : <http://example.org/> .\n")

        output_path = tmp_path / "manifest.json"
        manifest = register_dataset(
            root=data_dir,
            output=output_path,
            dataset_version="v1",
            source_variant="raw",
        )

        assert len(manifest.files) == 1
        assert manifest.files[0].relative_path == "brick.ttl"
        assert manifest.files[0].media_kind == "brick_ttl"

    def test_register_ignores_non_xlsx_ttl_files(self, tmp_path: Path) -> None:
        """Registration ignores files that are not .xlsx or .ttl."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])
        (data_dir / "readme.txt").write_text("readme")
        (data_dir / "data.csv").write_text("a,b\n1,2\n")
        (data_dir / "image.png").write_bytes(b"\x89PNG")

        manifest = register_dataset(
            root=data_dir,
            output=tmp_path / "manifest.json",
            dataset_version="v1",
            source_variant="raw",
        )

        assert len(manifest.files) == 1
        assert manifest.files[0].relative_path == "test.xlsx"

    def test_register_deterministic_path_ordering(self, tmp_path: Path) -> None:
        """Files are registered in deterministic sorted order."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        # Create files in non-alphabetical order
        _make_xlsx(data_dir / "zebra.xlsx", [[1]])
        _make_xlsx(data_dir / "alpha.xlsx", [[1]])
        _make_xlsx(data_dir / "beta.xlsx", [[1]])

        manifest = register_dataset(
            root=data_dir,
            output=tmp_path / "manifest.json",
            dataset_version="v1",
            source_variant="raw",
        )

        assert [f.relative_path for f in manifest.files] == [
            "alpha.xlsx",
            "beta.xlsx",
            "zebra.xlsx",
        ]

    def test_register_nested_directories(self, tmp_path: Path) -> None:
        """Registration recurses into subdirectories."""
        data_dir = tmp_path / "data"
        subdir = data_dir / "building1" / "floor2"
        subdir.mkdir(parents=True)
        _make_xlsx(subdir / "meter.xlsx", [[1]])

        manifest = register_dataset(
            root=data_dir,
            output=tmp_path / "manifest.json",
            dataset_version="v1",
            source_variant="raw",
        )

        assert len(manifest.files) == 1
        assert manifest.files[0].relative_path == "building1/floor2/meter.xlsx"

    def test_register_creates_output_parent(self, tmp_path: Path) -> None:
        """Registration creates output parent directory if needed."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])

        output_path = tmp_path / "output" / "subdir" / "manifest.json"
        manifest = register_dataset(
            root=data_dir,
            output=output_path,
            dataset_version="v1",
            source_variant="raw",
        )

        assert output_path.exists()
        assert manifest.dataset_version == "v1"

    def test_register_atomic_write(self, tmp_path: Path) -> None:
        """Manifest is written atomically to output path."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])

        output_path = tmp_path / "manifest.json"
        register_dataset(
            root=data_dir,
            output=output_path,
            dataset_version="v1",
            source_variant="raw",
        )

        assert output_path.exists()

    def test_register_byte_identical_json(self, tmp_path: Path) -> None:
        """Repeated registration produces byte-identical JSON."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1, 2]])

        output1 = tmp_path / "manifest1.json"
        output2 = tmp_path / "manifest2.json"

        register_dataset(
            root=data_dir,
            output=output1,
            dataset_version="v1",
            source_variant="raw",
        )
        register_dataset(
            root=data_dir,
            output=output2,
            dataset_version="v1",
            source_variant="raw",
        )

        assert output1.read_bytes() == output2.read_bytes()

    def test_register_json_canonical_format(self, tmp_path: Path) -> None:
        """JSON output is canonical with sorted keys and deterministic indentation."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])

        output_path = tmp_path / "manifest.json"
        register_dataset(
            root=data_dir,
            output=output_path,
            dataset_version="v1",
            source_variant="raw",
        )

        # Read and re-format with canonical settings
        data = json.loads(output_path.read_text())
        canonical = json.dumps(
            data,
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
        )
        canonical += "\n"  # Ensure trailing newline

        assert output_path.read_text() == canonical

    def test_register_json_no_absolute_paths(self, tmp_path: Path) -> None:
        """Serialized JSON contains no absolute local paths."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])

        output_path = tmp_path / "manifest.json"
        register_dataset(
            root=data_dir,
            output=output_path,
            dataset_version="v1",
            source_variant="raw",
        )

        json_text = output_path.read_text()
        # Check no absolute Windows or Unix paths in JSON
        assert str(tmp_path) not in json_text
        assert "C:\\" not in json_text
        assert "/tmp/" not in json_text

    def test_register_json_no_timestamps(self, tmp_path: Path) -> None:
        """Serialized JSON contains no execution timestamps."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])

        output_path = tmp_path / "manifest.json"
        register_dataset(
            root=data_dir,
            output=output_path,
            dataset_version="v1",
            source_variant="raw",
        )

        json_text = output_path.read_text()
        assert "timestamp" not in json_text.lower()
        assert "created" not in json_text.lower()
        assert "datetime" not in json_text.lower()

    def test_register_streamed_hash(self, tmp_path: Path) -> None:
        """SHA-256 is computed via streaming, not loading entire file."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        xlsx_path = data_dir / "test.xlsx"
        _make_xlsx(xlsx_path, [[1] * 100 for _ in range(100)])

        manifest = register_dataset(
            root=data_dir,
            output=tmp_path / "manifest.json",
            dataset_version="v1",
            source_variant="raw",
        )

        expected_hash = _file_sha256(xlsx_path)
        assert manifest.files[0].sha256 == expected_hash


class TestRawCleanValidation:
    """Tests for raw/clean source variant validation."""

    def test_raw_rejects_clean_in_path(self, tmp_path: Path) -> None:
        """Raw variant rejects path with 'clean' token."""
        data_dir = tmp_path / "data"
        clean_dir = data_dir / "clean" / "meter"
        clean_dir.mkdir(parents=True)
        _make_xlsx(clean_dir / "data.xlsx", [[1]])

        with pytest.raises(ValueError, match="clean"):
            register_dataset(
                root=data_dir,
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="raw",
            )

    def test_raw_rejects_cleaned_in_filename(self, tmp_path: Path) -> None:
        """Raw variant rejects file with 'cleaned' in name."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "meter_cleaned.xlsx", [[1]])

        with pytest.raises(ValueError, match="cleaned"):
            register_dataset(
                root=data_dir,
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="raw",
            )

    def test_raw_rejects_clean_in_filename(self, tmp_path: Path) -> None:
        """Raw variant rejects file with 'clean' in name."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "clean_data.xlsx", [[1]])

        with pytest.raises(ValueError, match="clean"):
            register_dataset(
                root=data_dir,
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="raw",
            )

    def test_raw_accepts_drawing_in_path(self, tmp_path: Path) -> None:
        """Raw variant does NOT reject path with 'drawing' (no false match)."""
        data_dir = tmp_path / "data"
        drawing_dir = data_dir / "drawing" / "meter"
        drawing_dir.mkdir(parents=True)
        _make_xlsx(drawing_dir / "data.xlsx", [[1]])

        # Should succeed - 'drawing' contains 'raw' substring but is not a match
        manifest = register_dataset(
            root=data_dir,
            output=tmp_path / "manifest.json",
            dataset_version="v1",
            source_variant="raw",
        )
        assert len(manifest.files) == 1

    def test_clean_rejects_raw_in_path(self, tmp_path: Path) -> None:
        """Clean variant rejects path with 'raw' token."""
        data_dir = tmp_path / "data"
        raw_dir = data_dir / "raw" / "meter"
        raw_dir.mkdir(parents=True)
        _make_xlsx(raw_dir / "data.xlsx", [[1]])

        with pytest.raises(ValueError, match="raw"):
            register_dataset(
                root=data_dir,
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="clean",
            )

    def test_clean_rejects_raw_in_filename(self, tmp_path: Path) -> None:
        """Clean variant rejects file with 'raw' in name."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "raw_data.xlsx", [[1]])

        with pytest.raises(ValueError, match="raw"):
            register_dataset(
                root=data_dir,
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="clean",
            )

    def test_clean_accepts_drawing_in_path(self, tmp_path: Path) -> None:
        """Clean variant does NOT reject path with 'drawing'."""
        data_dir = tmp_path / "data"
        drawing_dir = data_dir / "drawing" / "meter"
        drawing_dir.mkdir(parents=True)
        _make_xlsx(drawing_dir / "data.xlsx", [[1]])

        manifest = register_dataset(
            root=data_dir,
            output=tmp_path / "manifest.json",
            dataset_version="v1",
            source_variant="clean",
        )
        assert len(manifest.files) == 1

    def test_tokenization_uses_word_boundaries(self, tmp_path: Path) -> None:
        """Variant tokens are matched on word boundaries, not substrings."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # 'drawings' contains 'raw' but on non-word boundary, should be accepted
        drawings_dir = data_dir / "drawings"
        drawings_dir.mkdir()
        _make_xlsx(drawings_dir / "plan.xlsx", [[1]])

        # For raw variant - 'drawings' should not trigger rejection
        manifest = register_dataset(
            root=data_dir,
            output=tmp_path / "manifest.json",
            dataset_version="v1",
            source_variant="raw",
        )
        assert len(manifest.files) == 1


class TestSymlinkRejection:
    """Tests for symlink handling during registration."""

    @pytest.mark.skipif(
        not hasattr(Path, "symlink_to"),
        reason="Symlinks not supported on this platform",
    )
    def test_register_rejects_symlink_root(self, tmp_path: Path) -> None:
        """Registration rejects a root directory that is a symlink."""
        real_dir = tmp_path / "real_data"
        real_dir.mkdir()
        _make_xlsx(real_dir / "test.xlsx", [[1]])

        link_dir = tmp_path / "link_data"
        try:
            link_dir.symlink_to(real_dir)
        except OSError:
            pytest.skip("Symlink creation failed")

        with pytest.raises(ValueError, match="symlink"):
            register_dataset(
                root=link_dir,
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="raw",
            )

    @pytest.mark.skipif(
        not hasattr(Path, "symlink_to"),
        reason="Symlinks not supported on this platform",
    )
    def test_register_rejects_dangling_file_symlink(self, tmp_path: Path) -> None:
        """Registration rejects a dangling file symlink (target does not exist)."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        link_file = data_dir / "dangling.xlsx"
        try:
            link_file.symlink_to(data_dir / "nonexistent.xlsx")
        except OSError:
            pytest.skip("Symlink creation failed")

        with pytest.raises(ValueError, match="symlink"):
            register_dataset(
                root=data_dir,
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="raw",
            )

    @pytest.mark.skipif(
        not hasattr(Path, "symlink_to"),
        reason="Symlinks not supported on this platform",
    )
    def test_register_rejects_file_symlink(self, tmp_path: Path) -> None:
        """Registration rejects a file that is a symlink."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        real_file = data_dir / "real.xlsx"
        _make_xlsx(real_file, [[1]])

        link_file = data_dir / "link.xlsx"
        try:
            link_file.symlink_to(real_file)
        except OSError:
            pytest.skip("Symlink creation failed")

        with pytest.raises(ValueError, match="symlink"):
            register_dataset(
                root=data_dir,
                output=tmp_path / "manifest.json",
                dataset_version="v1",
                source_variant="raw",
            )

    @pytest.mark.skipif(
        not hasattr(Path, "symlink_to"),
        reason="Symlinks not supported on this platform",
    )
    def test_register_does_not_follow_directory_symlink(self, tmp_path: Path) -> None:
        """Registration does not follow directory symlinks."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        other_dir = tmp_path / "other"
        other_dir.mkdir()
        _make_xlsx(other_dir / "hidden.xlsx", [[1]])

        link_dir = data_dir / "link_dir"
        try:
            link_dir.symlink_to(other_dir)
        except OSError:
            pytest.skip("Symlink creation failed")

        # Create a real file in data_dir
        _make_xlsx(data_dir / "real.xlsx", [[1]])

        manifest = register_dataset(
            root=data_dir,
            output=tmp_path / "manifest.json",
            dataset_version="v1",
            source_variant="raw",
        )

        # Should only register real.xlsx, not hidden.xlsx via symlink
        assert len(manifest.files) == 1
        assert manifest.files[0].relative_path == "real.xlsx"


class TestManifestOutput:
    """Tests for manifest JSON output format."""

    def test_output_is_utf8(self, tmp_path: Path) -> None:
        """Manifest JSON is UTF-8 encoded."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])

        output_path = tmp_path / "manifest.json"
        register_dataset(
            root=data_dir,
            output=output_path,
            dataset_version="v1",
            source_variant="raw",
        )

        # Should decode as UTF-8
        content = output_path.read_text(encoding="utf-8")
        assert "dataset_version" in content

    def test_output_has_trailing_newline(self, tmp_path: Path) -> None:
        """Manifest JSON ends with a newline."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])

        output_path = tmp_path / "manifest.json"
        register_dataset(
            root=data_dir,
            output=output_path,
            dataset_version="v1",
            source_variant="raw",
        )

        content = output_path.read_text()
        assert content.endswith("\n")


class TestGlobalFileOrdering:
    """Tests for globally deterministic file ordering."""

    def test_nested_files_sorted_globally_by_posix_path(self, tmp_path: Path) -> None:
        """Files from nested directories are sorted globally by POSIX path."""
        data_dir = tmp_path / "data"
        # Create nested structure with files in multiple directories
        (data_dir / "z_dir").mkdir(parents=True)
        (data_dir / "a_dir" / "sub").mkdir(parents=True)
        (data_dir / "b_dir").mkdir(parents=True)

        _make_xlsx(data_dir / "z_dir" / "file.xlsx", [[1]])
        _make_xlsx(data_dir / "a_dir" / "sub" / "file.xlsx", [[1]])
        _make_xlsx(data_dir / "b_dir" / "file.xlsx", [[1]])
        _make_xlsx(data_dir / "root.xlsx", [[1]])

        manifest = register_dataset(
            root=data_dir,
            output=tmp_path / "manifest.json",
            dataset_version="v1",
            source_variant="raw",
        )

        # Files should be sorted by full relative POSIX path
        expected_order = [
            "a_dir/sub/file.xlsx",
            "b_dir/file.xlsx",
            "root.xlsx",
            "z_dir/file.xlsx",
        ]
        assert [f.relative_path for f in manifest.files] == expected_order

    def test_deeply_nested_vs_shallow_sorted_by_path(self, tmp_path: Path) -> None:
        """Deeply nested files sorted by full path, not by depth."""
        data_dir = tmp_path / "data"
        (data_dir / "a" / "b" / "c" / "d").mkdir(parents=True)
        (data_dir / "z").mkdir(parents=True)

        _make_xlsx(data_dir / "a" / "b" / "c" / "d" / "deep.xlsx", [[1]])
        _make_xlsx(data_dir / "z" / "shallow.xlsx", [[1]])

        manifest = register_dataset(
            root=data_dir,
            output=tmp_path / "manifest.json",
            dataset_version="v1",
            source_variant="raw",
        )

        # 'a/b/c/d/deep.xlsx' comes before 'z/shallow.xlsx'
        assert [f.relative_path for f in manifest.files] == [
            "a/b/c/d/deep.xlsx",
            "z/shallow.xlsx",
        ]


class TestManifestPathValidation:
    """Tests for manifest path safety validation."""

    def test_from_json_rejects_absolute_path(self, tmp_path: Path) -> None:
        """from_json rejects manifest with absolute path in relative_path."""
        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(
                FileManifest(
                    relative_path="/etc/passwd",
                    byte_size=100,
                    sha256="abc",
                    media_kind="workbook",
                ),
            ),
        )
        json_path = tmp_path / "manifest.json"
        manifest.to_json(json_path)

        root = tmp_path / "data"
        root.mkdir()

        with pytest.raises(ValueError, match="absolute path"):
            DatasetManifest.from_json(json_path, root=root)

    def test_from_json_rejects_dotdot_traversal(self, tmp_path: Path) -> None:
        """from_json rejects manifest with .. traversal in relative_path."""
        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(
                FileManifest(
                    relative_path="../../../etc/passwd",
                    byte_size=100,
                    sha256="abc",
                    media_kind="workbook",
                ),
            ),
        )
        json_path = tmp_path / "manifest.json"
        manifest.to_json(json_path)

        root = tmp_path / "data"
        root.mkdir()

        with pytest.raises(ValueError, match="dot-dot"):
            DatasetManifest.from_json(json_path, root=root)

    def test_from_json_rejects_dot_component(self, tmp_path: Path) -> None:
        """from_json rejects manifest with single dot component in path."""
        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(
                FileManifest(
                    relative_path="a/./b.xlsx",
                    byte_size=100,
                    sha256="abc",
                    media_kind="workbook",
                ),
            ),
        )
        json_path = tmp_path / "manifest.json"
        manifest.to_json(json_path)

        root = tmp_path / "data"
        root.mkdir()

        with pytest.raises(ValueError, match="dot component"):
            DatasetManifest.from_json(json_path, root=root)

    def test_from_json_rejects_trailing_dotdot(self, tmp_path: Path) -> None:
        """from_json rejects manifest with trailing .. component."""
        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(
                FileManifest(
                    relative_path="a/..",
                    byte_size=100,
                    sha256="abc",
                    media_kind="workbook",
                ),
            ),
        )
        json_path = tmp_path / "manifest.json"
        manifest.to_json(json_path)

        root = tmp_path / "data"
        root.mkdir()

        with pytest.raises(ValueError, match="dot-dot"):
            DatasetManifest.from_json(json_path, root=root)

    def test_from_json_rejects_empty_path(self, tmp_path: Path) -> None:
        """from_json rejects manifest with empty relative_path."""
        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(
                FileManifest(
                    relative_path="",
                    byte_size=100,
                    sha256="abc",
                    media_kind="workbook",
                ),
            ),
        )
        json_path = tmp_path / "manifest.json"
        manifest.to_json(json_path)

        root = tmp_path / "data"
        root.mkdir()

        with pytest.raises(ValueError, match="empty"):
            DatasetManifest.from_json(json_path, root=root)

    def test_from_json_rejects_symlink_file(self, tmp_path: Path) -> None:
        """from_json rejects if registered file is a symlink."""
        root = tmp_path / "data"
        root.mkdir()
        real_file = root / "real.xlsx"
        _make_xlsx(real_file, [[1]])

        link_file = root / "link.xlsx"
        try:
            link_file.symlink_to(real_file)
        except OSError:
            pytest.skip("Symlink creation failed")

        manifest = DatasetManifest(
            dataset_version="v1",
            source_variant="raw",
            files=(
                FileManifest(
                    relative_path="link.xlsx",
                    byte_size=real_file.stat().st_size,
                    sha256=_file_sha256(real_file),
                    media_kind="workbook",
                ),
            ),
        )
        json_path = tmp_path / "manifest.json"
        manifest.to_json(json_path)

        with pytest.raises(ValueError, match="symlink"):
            DatasetManifest.from_json(json_path, root=root)


class TestCLI:
    """Tests for CLI commands."""

    def test_cli_register_success(self, tmp_path: Path) -> None:
        """CLI register command succeeds with valid inputs."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])

        output_path = tmp_path / "manifest.json"
        from iot_energy_pipeline.cli import main

        result = main(
            [
                "register",
                "--root",
                str(data_dir),
                "--output",
                str(output_path),
                "--dataset-version",
                "v1",
                "--source-variant",
                "raw",
            ]
        )

        assert result == 0
        assert output_path.exists()

    def test_cli_register_missing_root_exits_2(self, tmp_path: Path) -> None:
        """CLI register exits 2 for missing root."""
        from iot_energy_pipeline.cli import main

        result = main(
            [
                "register",
                "--root",
                str(tmp_path / "missing"),
                "--output",
                str(tmp_path / "manifest.json"),
                "--dataset-version",
                "v1",
                "--source-variant",
                "raw",
            ]
        )

        assert result == 2

    def test_cli_register_no_absolute_paths_in_output(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """CLI register output never contains absolute local paths."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [[1]])

        output_path = tmp_path / "manifest.json"
        from iot_energy_pipeline.cli import main

        # Pass absolute paths as arguments
        result = main(
            [
                "register",
                "--root",
                str(data_dir.resolve()),
                "--output",
                str(output_path.resolve()),
                "--dataset-version",
                "v1",
                "--source-variant",
                "raw",
            ]
        )

        assert result == 0
        captured = capsys.readouterr()
        # Output should not contain the absolute local path
        assert str(tmp_path) not in captured.out
        assert "C:\\" not in captured.out

    def test_cli_profile_success(self, tmp_path: Path) -> None:
        """CLI profile command succeeds with valid inputs."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [["a", "b"], [1, 2]])

        manifest_path = tmp_path / "manifest.json"
        output_path = tmp_path / "profile.json"
        from iot_energy_pipeline.cli import main

        main(
            [
                "register",
                "--root",
                str(data_dir),
                "--output",
                str(manifest_path),
                "--dataset-version",
                "v1",
                "--source-variant",
                "raw",
            ]
        )

        result = main(
            [
                "profile",
                "--manifest",
                str(manifest_path),
                "--root",
                str(data_dir),
                "--output",
                str(output_path),
            ]
        )

        assert result == 0
        assert output_path.exists()

    def test_cli_profile_no_absolute_paths_in_output(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """CLI profile output never contains absolute local paths."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _make_xlsx(data_dir / "test.xlsx", [["a"], [1]])

        manifest_path = tmp_path / "manifest.json"
        output_path = tmp_path / "profile.json"
        from iot_energy_pipeline.cli import main

        main(
            [
                "register",
                "--root",
                str(data_dir),
                "--output",
                str(manifest_path),
                "--dataset-version",
                "v1",
                "--source-variant",
                "raw",
            ]
        )

        result = main(
            [
                "profile",
                "--manifest",
                str(manifest_path.resolve()),
                "--root",
                str(data_dir.resolve()),
                "--output",
                str(output_path.resolve()),
            ]
        )

        assert result == 0
        captured = capsys.readouterr()
        assert str(tmp_path) not in captured.out
        assert "C:\\" not in captured.out

    def test_cli_profile_missing_manifest_exits_2(self, tmp_path: Path) -> None:
        """CLI profile exits 2 for missing manifest."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        from iot_energy_pipeline.cli import main

        result = main(
            [
                "profile",
                "--manifest",
                str(tmp_path / "missing.json"),
                "--root",
                str(data_dir),
                "--output",
                str(tmp_path / "profile.json"),
            ]
        )

        assert result == 2
