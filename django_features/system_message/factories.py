import datetime

from factory import SubFactory
from factory.django import DjangoModelFactory
from pytz import UTC

from django_features.system_message import models


class SystemMessageTypeFactory(DjangoModelFactory):
    class Meta:
        model = models.SystemMessageType

    name = "Info"
    icon = "information"


class SystemMessageFactory(DjangoModelFactory):
    class Meta:
        model = models.SystemMessage

    background_color = "#008DCC"
    begin = datetime.datetime(2025, 1, 1, tzinfo=UTC)
    text = "Hello World!"
    title = "System Info"
    type = SubFactory(SystemMessageTypeFactory)  # type: ignore
