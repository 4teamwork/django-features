from typing import Any

from constance import config
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.request import Request


class CanManageSystemMessage(DjangoModelPermissions):
    allowed_actions = ["list", "retrieve"]

    def has_permission(self, request: Request, view: Any) -> bool:
        if not config.ENABLE_SYSTEM_MESSAGE:
            return False
        if view.action in self.allowed_actions:
            return True
        perm = config.SYSTEM_MESSAGE_PERMISSION
        if not perm:
            return True
        return request.user.is_superuser or request.user.has_perm(perm)
