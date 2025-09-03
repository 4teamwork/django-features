from typing import Any

from factory.django import DjangoModelFactory


class BaseFactory(DjangoModelFactory):
    class Meta:
        abstract = True

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        return super().__new__(*args, **kwargs)  # type: ignore
