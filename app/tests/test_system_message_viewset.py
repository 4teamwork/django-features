import datetime

import pytz
from constance.test import override_config
from freezegun import freeze_time
from pluck import pluck

from app.tests import APITestCase
from app.tests.factories.factories import SystemMessageFactory


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
