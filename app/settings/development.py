from app.settings.base import Base


class Development(Base):
    DEBUG = True
    SECRET_KEY = "secret"
