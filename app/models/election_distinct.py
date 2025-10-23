from django.db import models
from django_extensions.db.models import TimeStampedModel


class ElectionDistrict(TimeStampedModel):
    uid = models.UUIDField(verbose_name="UUID", unique=True)
    title = models.CharField(verbose_name="Title", unique=True)
    number = models.CharField(verbose_name="Number")

    class Meta:
        verbose_name = "Election district"
        verbose_name_plural = "Election districts"
        ordering = ("title",)

    def __str__(self) -> str:
        return "{} - {}".format(self.number, self.title)
