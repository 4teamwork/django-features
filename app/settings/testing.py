from configurations import values

from app.settings.base import Base


class Testing(Base):
    SECRET_KEY = "secret"

    DATABASE_NAME = values.Value("django_features_testing")
    DATABASE_ENGINE = values.Value("django.db.backends.postgresql")
    DATABASE_USER = values.Value("postgres")
    DATABASE_PASSWORD = values.Value("postgres")
    DATABASE_HOST = values.Value("127.0.0.1")
    DATABASE_PORT = values.Value("5432")
    DATABASE_OPTIONS = values.DictValue({})
