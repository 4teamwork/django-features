from rest_framework import serializers

from django_features.system_message import models


class SystemMessageTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SystemMessageType
        fields = [
            "id",
            "icon",
            "name",
        ]


class SystemMessageSerializer(serializers.ModelSerializer):
    type = SystemMessageTypeSerializer(read_only=True)
    type_id = serializers.IntegerField()

    class Meta:
        model = models.SystemMessage
        fields = [
            "background_color",
            "begin",
            "end",
            "id",
            "text",
            "text_color",
            "title",
            "type",
            "type_id",
        ]
