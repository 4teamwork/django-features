import json
from typing import Any

from django.forms import fields


class PrettyJSONEncoder(json.JSONEncoder):
    def __init__(self, *args: Any, indent: int, sort_keys: bool, **kwargs: Any) -> None:
        super().__init__(*args, indent=2, **kwargs)


class PrettyJSONField(fields.JSONField):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["encoder"] = PrettyJSONEncoder
        super().__init__(*args, **kwargs)
