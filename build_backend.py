"""PEP 517 build backend that compiles gettext catalogs for package artifacts."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from typing import Iterator

import polib
from poetry.core.masonry import api as poetry_api


get_requires_for_build_wheel = poetry_api.get_requires_for_build_wheel
get_requires_for_build_sdist = poetry_api.get_requires_for_build_sdist
get_requires_for_build_editable = poetry_api.get_requires_for_build_editable
prepare_metadata_for_build_wheel = poetry_api.prepare_metadata_for_build_wheel
prepare_metadata_for_build_editable = poetry_api.prepare_metadata_for_build_editable


@contextmanager
def _compiled_catalogs() -> Iterator[None]:
    """Compile every PO catalog and restore the source tree after the build."""
    project_root = Path(__file__).resolve().parent
    po_paths = sorted(
        (project_root / "django_features" / "locale").glob("*/LC_MESSAGES/*.po")
    )
    if not po_paths:
        raise RuntimeError("No gettext catalogs were found to compile.")

    original_mo_contents: dict[Path, bytes | None] = {}
    try:
        for po_path in po_paths:
            mo_path = po_path.with_suffix(".mo")
            original_mo_contents[mo_path] = (
                mo_path.read_bytes() if mo_path.exists() else None
            )
            catalog = polib.pofile(str(po_path), encoding="utf-8")
            catalog.save_as_mofile(str(mo_path))
        yield
    finally:
        for mo_path, original_content in original_mo_contents.items():
            if original_content is None:
                mo_path.unlink(missing_ok=True)
            else:
                mo_path.write_bytes(original_content)


def _build_with_catalogs(
    build: Callable[..., str],
    *args: Any,
    **kwargs: Any,
) -> str:
    with _compiled_catalogs():
        return build(*args, **kwargs)


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _build_with_catalogs(
        poetry_api.build_wheel,
        wheel_directory,
        config_settings,
        metadata_directory,
    )


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, Any] | None = None,
) -> str:
    return _build_with_catalogs(
        poetry_api.build_sdist,
        sdist_directory,
        config_settings,
    )


def build_editable(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _build_with_catalogs(
        poetry_api.build_editable,
        wheel_directory,
        config_settings,
        metadata_directory,
    )
