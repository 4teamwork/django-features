from django.db import models
from django_extensions.db.models import TimeStampedModel


class Municipality(TimeStampedModel):
    title = models.CharField(verbose_name="title", unique=True)

    class Meta:
        verbose_name = "Municipality"
        verbose_name_plural = "Municipalities"

    def __str__(self) -> str:
        return self.title
