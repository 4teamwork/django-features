import datetime

from factory import SubFactory
from pytz import UTC

from app.tests.factories import BaseFactory
from django_features.system_message import models


class SystemMessageTypeFactory(BaseFactory):
    class Meta:
        model = models.SystemMessageType

    name = "Info"
    icon = "information"


class SystemMessageFactory(BaseFactory):
    class Meta:
        model = models.SystemMessage

    background_color = "#008DCC"
    begin = datetime.datetime(2025, 1, 1, tzinfo=UTC)
    text = "Hello World!"
    title = "System Info"
    type = SubFactory(SystemMessageTypeFactory)  # type: ignore
