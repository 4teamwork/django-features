class SystemMessageConfigurationMixin:
    @property
    def CONSTANCE_CONFIG(self) -> dict:
        return {
            "SYSTEM_MESSAGE_PERMISSION": (
                "",
                "Django permission to manage system messages.",
                str,
            ),
            "ENABLE_SYSTEM_MESSAGE": (False, "Enables the system info feature.", bool),
        }

    @property
    def CONSTANCE_CONFIG_FIELDSETS(self) -> dict:
        return {
            "System messages": {
                "fields": ("ENABLE_SYSTEM_MESSAGE", "SYSTEM_MESSAGE_PERMISSION"),
                "collapse": True,
            },
        }
