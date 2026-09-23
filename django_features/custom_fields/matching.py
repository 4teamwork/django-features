"""Request-local, exact matching of an explicitly selected choice attribute."""

from collections.abc import Callable
from collections.abc import Iterable
from typing import Any

from modeltranslation.settings import AVAILABLE_LANGUAGES
from modeltranslation.utils import build_localized_fieldname
from rest_framework.exceptions import ValidationError

from django_features.custom_fields.models.value import AbstractBaseCustomValue


class ChoiceMatchError(ValidationError):
    """A safe matching error; detail never includes choice values."""


class ChoiceMatcher:
    def __init__(
        self,
        choices: Iterable[AbstractBaseCustomValue],
        *,
        attribute: str,
        language: str | None = None,
        normalize: Callable[[Any], Any] | None = None,
    ) -> None:
        if attribute not in ("label", "value", "external_label"):
            raise ValueError("Unsupported matching attribute.")
        if attribute == "label":
            if language not in AVAILABLE_LANGUAGES:
                raise ValueError("Select a supported label language.")
            attribute = build_localized_fieldname("label", language)
        elif language is not None:
            raise ValueError("Language applies only to labels.")
        self.normalize = normalize
        self._index: dict[Any, AbstractBaseCustomValue] = {}
        self._ambiguous: set[Any] = set()
        for choice in choices:
            key = self._key(getattr(choice, attribute))
            if key in (None, ""):
                continue
            try:
                if key in self._index:
                    self._ambiguous.add(key)
                self._index[key] = choice
            except TypeError:
                raise ChoiceMatchError(
                    "Unhashable choice value.", code="type_mismatch"
                ) from None

    def _key(self, value: Any) -> Any:
        return self.normalize(value) if self.normalize is not None else value

    def resolve(self, token: Any) -> AbstractBaseCustomValue:
        key = self._key(token)
        try:
            if key in self._ambiguous:
                raise ChoiceMatchError(
                    "More than one choice matches.", code="ambiguous"
                )
            return self._index[key]
        except TypeError:
            raise ChoiceMatchError("Unhashable token.", code="type_mismatch") from None
        except KeyError:
            raise ChoiceMatchError("No choice matches.", code="missing") from None

    def resolve_many(self, tokens: Iterable[Any]) -> list[AbstractBaseCustomValue]:
        return [self.resolve(token) for token in tokens]
