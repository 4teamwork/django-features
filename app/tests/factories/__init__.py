import uuid
from typing import Any

from factory import LazyFunction  # type: ignore
from factory import SubFactory  # type: ignore
from factory.django import DjangoModelFactory

from app import models


class BaseFactory(DjangoModelFactory):
    class Meta:
        abstract = True

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        return super().__new__(*args, **kwargs)  # type: ignore


class PersonTypeFactory(BaseFactory):
    class Meta:
        model = models.PersonType

    title = "Type 1"


class PersonFactory(BaseFactory):
    class Meta:
        model = models.Person

    firstname = "John"
    lastname = "Doe"
    email = "john.doe@example.com"


class ElectionDistrictFactory(BaseFactory):
    class Meta:
        model = models.ElectionDistrict

    uid = LazyFunction(lambda: uuid.uuid4())  # type: ignore
    number = "1"
    title = "Election District 1"


class AddressFactory(BaseFactory):
    class Meta:
        model = models.Address

    city = "New York"
    country = "USA"
    street = "123 Main St"
    external_uid = LazyFunction(lambda: uuid.uuid4())  # type: ignore
    zip_code = "10001"

    target = SubFactory(PersonFactory)  # type: ignore
