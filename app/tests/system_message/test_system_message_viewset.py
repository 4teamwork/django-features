import datetime

import pytz
from constance.test import override_config
from django.contrib.auth.models import Permission
from freezegun import freeze_time
from pluck import pluck

from app.tests import APITestCase
from app.tests.system_message.factories import SystemMessageFactory
from app.tests.system_message.factories import SystemMessageTypeFactory


class SystemInfoViewSetTest(APITestCase):
    @override_config(ENABLE_SYSTEM_MESSAGE=True)
    def test_filter_active_system_infos(self) -> None:
        past = SystemMessageFactory(
            title="past",
            begin=datetime.datetime(2024, 1, 1, tzinfo=pytz.UTC),
            end=datetime.datetime(2024, 12, 31, 23, 59, 59, tzinfo=pytz.UTC),
        )
        active_1 = SystemMessageFactory(
            title="active 1",
            begin=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=pytz.UTC),
        )
        active_2 = SystemMessageFactory(
            title="active 2",
            begin=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=pytz.UTC),
            end=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=pytz.UTC),
        )
        future = SystemMessageFactory(
            title="future",
            begin=datetime.datetime(2025, 1, 1, 0, 0, 1, tzinfo=pytz.UTC),
        )

        with freeze_time(datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)):
            response = self.client.get("/api/system_message?active=true")

        data = response.json()
        self.assertEqual(2, len(data))
        self.assertEqual([active_2.title, active_1.title], pluck(data, "title"))

        with freeze_time(datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)):
            response = self.client.get("/api/system_message?active=false")

        data = response.json()
        self.assertEqual(2, len(data))
        self.assertEqual([past.title, future.title], pluck(data, "title"))

    @override_config(ENABLE_SYSTEM_MESSAGE=True)
    def test_filter_dismissed_system_infos(self) -> None:
        info_1 = SystemMessageFactory(title="dismissed")
        info_2 = SystemMessageFactory(title="not")
        info_1.dismissed_users.add(self.user)

        response = self.client.get("/api/system_message?dismissed=false")

        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual([info_2.title], pluck(data, "title"))

        response = self.client.get("/api/system_message?dismissed=true")

        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual([info_1.title], pluck(data, "title"))

    @override_config(
        ENABLE_SYSTEM_MESSAGE=True,
        SYSTEM_MESSAGE_PERMISSION="system_message.change_systemmessage",
    )
    def test_system_message_viewset_permission(self) -> None:
        system_message_type = SystemMessageTypeFactory()

        data = {
            "begin": "2025-10-01T04:50:49.592Z",
            "text_color": "#FFFFFF",
            "background_color": "#0000FF",
            "title": "Hello World",
            "type_id": system_message_type.id,
            "text": "Test",
        }

        self.assertFalse(self.user.has_perm("system_message.change_systemmessage"))

        response = self.client.get("/api/system_message")
        self.assertEqual(200, response.status_code)

        response = self.client.post("/api/system_message", data)
        self.assertEqual(403, response.status_code)

        self.user.user_permissions.add(
            Permission.objects.get(codename="change_systemmessage")
        )

        response = self.client.post("/api/system_message", data)
        self.assertEqual(201, response.status_code)
