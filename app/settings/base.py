from pathlib import Path

from configurations import Configuration
from configurations import values
from django.utils.translation import gettext_lazy as _


class Base(Configuration):
    DEBUG = False

    @property
    def INSTALLED_APPS(self) -> list[str]:
        installed_apps = [
            "modeltranslation",
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.messages",
            "django.contrib.sessions",
            "django_extensions",
            "django_linear_migrations",
            "constance",
            "rest_framework",
            "django_features.system_message",
        ]
        return installed_apps

    BASE_DIR = Path(__file__).parent.parent.parent
    DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

    @property
    def MIDDLEWARE(self) -> list[str]:
        middlewares = [
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.locale.LocaleMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
        ]
        return middlewares

    AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
    ROOT_URLCONF = "app.urls"

    TIME_ZONE = "Europe/Zurich"
    USE_I18N = True
    USE_L10N = True
    USE_TZ = True

    LANGUAGE_CODE = "de"
    LANGUAGES = [
        ("de", _("Deutsch")),
        ("en", _("Englisch")),
        ("fr", _("Französisch")),
    ]
    LOCALE_PATHS = [
        BASE_DIR / "django_features" / "locale",
    ]

    DATABASE_NAME = values.Value("django_features")
    DATABASE_ENGINE = values.Value("django.db.backends.postgresql")
    DATABASE_USER = values.Value("")
    DATABASE_PASSWORD = values.Value("")
    DATABASE_HOST = values.Value("")
    DATABASE_PORT = values.Value("")
    DATABASE_OPTIONS = values.DictValue({})

    @property
    def DATABASES(self) -> dict:
        return {
            "default": {
                "ENGINE": self.DATABASE_ENGINE,
                "NAME": self.DATABASE_NAME,
                "USER": self.DATABASE_USER,
                "PASSWORD": self.DATABASE_PASSWORD,
                "HOST": self.DATABASE_HOST,
                "PORT": self.DATABASE_PORT,
                "OPTIONS": self.DATABASE_OPTIONS,
                "ATOMIC_REQUESTS": True,
            }
        }

    TEMPLATES = [
        {
            "APP_DIRS": True,
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [],
            "OPTIONS": {
                "context_processors": [
                    "django.template.context_processors.debug",
                    "django.template.context_processors.request",
                    "django.contrib.auth.context_processors.auth",
                    "django.contrib.messages.context_processors.messages",
                ]
            },
        }
    ]

    REST_FRAMEWORK = {
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.SessionAuthentication"
        ],
        "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    }

    CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

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
            "Miscellaneous": {
                "fields": ("ENABLE_SYSTEM_MESSAGE", "SYSTEM_MESSAGE_PERMISSION"),
                "collapse": True,
            },
        }

    SECRET_KEY = values.SecretValue()
