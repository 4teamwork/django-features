from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from app.custom_field import models


@register(models.CustomField)
class CustomFieldTranslationOptions(TranslationOptions):
    fields = ("label",)


@register(models.CustomValue)
class CustomChoiceTranslationOptions(TranslationOptions):
    fields = ("label",)
