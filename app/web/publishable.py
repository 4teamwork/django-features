from django.db import models
from django_extensions.db.models import TimeStampedModel


class PublishableQuerySet(models.QuerySet):
    def publishable(self) -> "PublishableQuerySet":
        return self.filter(is_public=True)


class PublishableModel(TimeStampedModel):
    is_public = models.BooleanField(default=False)

    class Meta:
        abstract = True
