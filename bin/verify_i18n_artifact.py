"""Build clean release artifacts and verify their compiled gettext catalogs."""

from __future__ import annotations

import gettext
import io
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_TRANSLATIONS = {
    "de": (
        "This custom field may not be changed manually.",
        "Dieses benutzerdefinierte Feld darf nicht manuell geändert werden.",
    ),
    "en": ("Objekt existiert nicht.", "Object does not exist."),
    "fr": (
        "This custom field may not be changed manually.",
        "Ce champ personnalisé ne peut pas être modifié manuellement.",
    ),
}


def _ignored_paths(_directory: str, names: list[str]) -> set[str]:
    ignored_names = {
        ".git",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".venv",
        "__pycache__",
        "dist",
    }
    return {
        name
        for name in names
        if name in ignored_names or name.endswith((".mo", ".pyc"))
    }


def _verify_wheel(wheel_path: Path) -> None:
    with zipfile.ZipFile(wheel_path) as wheel:
        for locale, (message, expected) in EXPECTED_TRANSLATIONS.items():
            catalog_path = f"django_features/locale/{locale}/LC_MESSAGES/django.mo"
            catalog = gettext.GNUTranslations(fp=io.BytesIO(wheel.read(catalog_path)))
            actual = catalog.gettext(message)
            if actual != expected:
                raise AssertionError(
                    f"Unexpected {locale} translation for {message!r}: "
                    f"{actual!r} != {expected!r}"
                )


def _only_wheel(directory: Path) -> Path:
    wheels = list(directory.glob("*.whl"))
    if len(wheels) != 1:
        raise AssertionError(f"Expected one wheel in {directory}, found: {wheels}")
    return wheels[0]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="django-features-i18n-") as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "source"
        pep517_path = temp_path / "pep517-wheel"
        poetry_path = temp_path / "poetry-wheel"
        shutil.copytree(PROJECT_ROOT, source_path, ignore=_ignored_paths)
        pep517_path.mkdir()
        poetry_path.mkdir()

        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--outdir",
                str(pep517_path),
                str(source_path),
            ],
            check=True,
        )
        pep517_wheel = _only_wheel(pep517_path)
        _verify_wheel(pep517_wheel)

        poetry = shutil.which("poetry")
        if poetry is None:
            raise RuntimeError("Poetry is required to verify the release build path.")
        subprocess.run(
            [
                poetry,
                "build",
                "--format",
                "wheel",
                "--output",
                str(poetry_path),
            ],
            cwd=source_path,
            check=True,
        )
        poetry_wheel = _only_wheel(poetry_path)
        _verify_wheel(poetry_wheel)

        unexpected_catalogs = list(source_path.rglob("*.mo"))
        if unexpected_catalogs:
            raise AssertionError(
                f"Build backend left generated catalogs behind: {unexpected_catalogs}"
            )

        print(
            "Verified compiled translations in PEP 517 and Poetry wheels: "
            f"{pep517_wheel.name}, {poetry_wheel.name}"
        )


if __name__ == "__main__":
    main()
