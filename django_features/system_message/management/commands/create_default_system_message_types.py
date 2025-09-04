import json
from typing import Any

import djclick as click
from django.core.management import CommandParser
from django.core.management.base import BaseCommand

from django_features.system_message import models


DEFAULT_SYSTEM_MESSAGE_TYPES = [
    {
        "name": "Info",
        "icon": "information",
    },
    {
        "name": "Warning",
        "icon": "alert",
    },
    {
        "name": "Error",
        "icon": "alert-octagon",
    },
]


class Command(BaseCommand):
    help = "Creates or updates default system message types."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--types",
            type=str,
            help="List of objects with the name and icon of the system message types.",
        )

    def handle(self, types: str, *args: Any, **options: Any) -> None:
        data = DEFAULT_SYSTEM_MESSAGE_TYPES
        if types is not None:
            data = json.loads(types)

        for message_type_data in data:
            name = message_type_data.get("name")

            if not name:
                click.secho(
                    f"ERROR: {message_type_data} has no attribute name", fg="red"
                )

            icon = message_type_data.get("icon")
            info_type, created = models.SystemMessageType.objects.get_or_create(
                name=name
            )
            info_type.icon = icon
            info_type.save()

            click.secho(
                f"INFO: Updated system message type {name} with icon {icon}",
                fg="yellow" if not icon else "green",
            )
