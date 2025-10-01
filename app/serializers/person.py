from app.models import Person
from django_features.custom_fields.serializers import CustomFieldBaseModelSerializer


class PersonSerializer(CustomFieldBaseModelSerializer):
    class Meta:
        model = Person
        fields = [
            "email",
            "firstname",
            "lastname",
        ]
