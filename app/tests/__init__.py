from typing import Any

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from django_features.custom_fields.helpers import clear_custom_field_model_cache


User = get_user_model()


class APITestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        super().setUp()
        self.anonymous_client = APIClient()
        self.client = APIClient()
        self.login("kathi.barfuss")
        self.session = self.client.session

    def tearDown(self) -> None:
        super().tearDown()
        clear_custom_field_model_cache()

    def get_or_create_user(self, username: str) -> tuple[Any, bool]:
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password("secret")
            user.save()
        return user, created

    def login(self, username: str, password: str = "secret") -> None:
        self.user, _ = self.get_or_create_user(username=username)
        self.client.login(username=username, password=password)
