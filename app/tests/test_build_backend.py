from pathlib import Path

import polib  # type: ignore[import-untyped]
import pytest
from poetry.core.masonry import api as poetry_api

import build_backend


def create_catalog(project_root: Path) -> tuple[Path, Path]:
    locale_directory = project_root / "django_features/locale/de/LC_MESSAGES"
    locale_directory.mkdir(parents=True)
    po_path = locale_directory / "django.po"
    catalog = polib.POFile()
    catalog.metadata = {
        "Content-Type": "text/plain; charset=UTF-8",
        "Language": "de",
    }
    catalog.append(polib.POEntry(msgid="Hello", msgstr="Hallo"))
    catalog.save(po_path)
    return po_path, po_path.with_suffix(".mo")


def test_compiled_catalogs_removes_new_artifacts(tmp_path: Path) -> None:
    _po_path, mo_path = create_catalog(tmp_path)

    with build_backend._compiled_catalogs(tmp_path):
        assert mo_path.exists()
        assert mo_path.stat().st_size > 0

    assert not mo_path.exists()


def test_compiled_catalogs_restores_existing_artifact_after_failure(
    tmp_path: Path,
) -> None:
    _po_path, mo_path = create_catalog(tmp_path)
    original_content = b"existing compiled catalog"
    mo_path.write_bytes(original_content)

    with pytest.raises(RuntimeError, match="build failed"):
        with build_backend._compiled_catalogs(tmp_path):
            assert mo_path.read_bytes() != original_content
            raise RuntimeError("build failed")

    assert mo_path.read_bytes() == original_content


def test_compiled_catalogs_requires_source_catalogs(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="No gettext catalogs"):
        with build_backend._compiled_catalogs(tmp_path):
            pass


def test_editable_build_does_not_compile_temporary_source_catalogs() -> None:
    assert build_backend.build_editable is poetry_api.build_editable
