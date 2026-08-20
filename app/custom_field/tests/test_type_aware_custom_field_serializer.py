from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers

from app.custom_field.tests.factories import CustomFieldFactory
from app.custom_field.tests.factories import CustomValueFactory
from app.custom_field.tests.serializers import HookedPersonSerializer
from app.custom_field.tests.serializers import TypeAwarePersonSerializer
from app.custom_field.tests.serializers import TypeIdPersonSerializer
from app.models import Municipality
from app.models import Person
from app.models import PersonType
from app.serializers.person import PersonSerializer
from app.tests import APITestCase
from app.tests.factories import PersonFactory
from app.tests.factories import PersonTypeFactory
from django_features.serializers import MappingSerializer


class SlugTypePersonSerializer(TypeAwarePersonSerializer):
    person_type = serializers.SlugRelatedField(
        slug_field="title",
        queryset=PersonType.objects.all(),
        required=False,
    )


class ScalarTypeIdPersonSerializer(TypeAwarePersonSerializer):
    custom_field_type_input_field = "type_id"

    type_id = serializers.IntegerField(
        allow_null=True,
        required=False,
        source="person_type_id",
    )

    class Meta:
        model = Person
        fields = ["email", "firstname", "lastname", "type_id"]


class TypeAwarePersonMappingSerializer(MappingSerializer):
    person_type = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        queryset=PersonType.objects.all(),
        required=False,
    )

    class Meta:
        model = Person
        fields = "__all__"

    @property
    def mapping(self) -> dict[str, dict[str, Any]]:
        return getattr(
            self,
            "_mapping",
            {
                "person": {
                    "external_firstname": "firstname",
                    "external_type": "person_type",
                    "external_default": "default_value",
                    "external_first": "first_value",
                    "external_second": "second_value",
                }
            },
        )

    @mapping.setter
    def mapping(self, value: dict[str, dict[str, Any]]) -> None:
        self._mapping = value


class TypeAwareCustomFieldSerializerTest(APITestCase):
    def setUp(self) -> None:
        self.type_ct = ContentType.objects.get_for_model(PersonType)
        self.first_type = PersonTypeFactory(title="First")
        self.second_type = PersonTypeFactory(title="Second")
        self.default_field = CustomFieldFactory(identifier="default_value")
        self.first_field = CustomFieldFactory(
            identifier="first_value",
            type_content_type=self.type_ct,
            type_id=self.first_type.id,
        )
        self.second_field = CustomFieldFactory(
            identifier="second_value",
            type_content_type=self.type_ct,
            type_id=self.second_type.id,
        )

    def test_custom_type_input_field_defaults_to_model_type_attribute(self) -> None:
        serializer = TypeAwarePersonSerializer()

        self.assertEqual(serializer.custom_field_type_input_field, "person_type")

    def test_custom_filter_is_preserved(self) -> None:
        serializer = TypeAwarePersonSerializer()
        serializer.filter = {"identifier": "default_value"}

        self.assertIn("default_value", serializer.fields)
        self.assertNotIn("first_value", serializer.fields)

    def test_custom_fields_queryset_hook_controls_dynamic_fields(self) -> None:
        CustomFieldFactory(identifier="included")

        serializer = HookedPersonSerializer()

        self.assertIn("included", serializer.fields)
        self.assertNotIn("default_value", serializer.fields)

    def test_create_uses_type_from_default_input_field(self) -> None:
        serializer = TypeAwarePersonSerializer(
            data={
                "firstname": "First",
                "person_type": self.first_type.id,
                "default_value": "default",
                "first_value": "typed",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertSetEqual(
            set(serializer.fields),
            {
                "email",
                "firstname",
                "lastname",
                "person_type",
                "default_value",
                "first_value",
            },
        )
        person = serializer.save()
        self.assertEqual(person.person_type, self.first_type)

    def test_custom_type_input_field_can_be_overridden(self) -> None:
        serializer = TypeIdPersonSerializer(
            data={
                "firstname": "First",
                "type_id": self.first_type.id,
                "first_value": "typed",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn("first_value", serializer.fields)
        self.assertNotIn("second_value", serializer.fields)
        person = serializer.save()
        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(
            person.custom_values.filter(field=self.first_field, value="typed").exists()
        )

    def test_slug_related_type_input_selects_and_persists_typed_fields(self) -> None:
        serializer = SlugTypePersonSerializer(
            data={
                "firstname": "Slug",
                "person_type": self.first_type.title,
                "first_value": "typed",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(
            person.custom_values.filter(field=self.first_field, value="typed").exists()
        )

    def test_slug_related_type_input_updates_the_selected_type(self) -> None:
        person = PersonFactory(person_type=self.first_type)
        serializer = SlugTypePersonSerializer(
            person,
            data={
                "person_type": self.second_type.title,
                "second_value": "typed",
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(person.person_type, self.second_type)
        self.assertTrue(person.custom_values.filter(field=self.second_field).exists())

    def test_slug_related_type_input_runs_field_validators_once(self) -> None:
        calls = []

        def track_validation(value: PersonType) -> None:
            calls.append(value)

        class ValidatedSlugTypePersonSerializer(TypeAwarePersonSerializer):
            person_type = serializers.SlugRelatedField(
                slug_field="title",
                queryset=PersonType.objects.all(),
                validators=[track_validation],
            )

        serializer = ValidatedSlugTypePersonSerializer(
            data={
                "firstname": "Slug",
                "person_type": self.first_type.title,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(calls, [self.first_type])

    def test_invalid_slug_preserves_the_selector_error(self) -> None:
        serializer = SlugTypePersonSerializer(
            data={
                "firstname": "Invalid slug",
                "person_type": "missing",
                "first_value": "must not be accepted",
            }
        )

        self.assertNotIn("first_value", serializer.fields)
        with self.assertNumQueries(0):
            is_valid = serializer.is_valid()

        self.assertFalse(is_valid)
        self.assertEqual(serializer.errors["person_type"][0].code, "does_not_exist")
        self.assertNotIn("first_value", serializer.errors)

    def test_scalar_type_id_source_selects_and_persists_typed_fields(self) -> None:
        serializer = ScalarTypeIdPersonSerializer(
            data={
                "firstname": "Scalar ID",
                "type_id": self.first_type.id,
                "first_value": "typed",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(
            person.custom_values.filter(field=self.first_field, value="typed").exists()
        )

    def test_scalar_type_id_source_rejects_a_nonexistent_type(self) -> None:
        serializer = ScalarTypeIdPersonSerializer(
            data={"firstname": "Missing", "type_id": 999_999}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["type_id"][0].code, "invalid")

    def test_scalar_type_id_source_accepts_null(self) -> None:
        person = PersonFactory(person_type=self.first_type)
        serializer = ScalarTypeIdPersonSerializer(
            person,
            data={"type_id": None, "default_value": "global"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertIsNone(person.person_type)
        self.assertTrue(person.custom_values.filter(field=self.default_field).exists())

    def test_related_field_cannot_map_to_the_foreign_key_attname(self) -> None:
        class RelatedTypeIdPersonSerializer(TypeAwarePersonSerializer):
            custom_field_type_input_field = "type_id"
            type_id = serializers.PrimaryKeyRelatedField(
                queryset=PersonType.objects.all(),
                source="person_type_id",
            )

            class Meta:
                model = Person
                fields = ["firstname", "type_id"]

        serializer = RelatedTypeIdPersonSerializer(
            data={"firstname": "Invalid source", "type_id": self.first_type.id}
        )

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "must validate to a primary key or None, not a model instance",
        ):
            serializer.is_valid()

    def test_scalar_field_cannot_map_to_the_model_relation(self) -> None:
        class ScalarRelationPersonSerializer(TypeAwarePersonSerializer):
            custom_field_type_input_field = "type_id"
            type_id = serializers.IntegerField(source="person_type")

            class Meta:
                model = Person
                fields = ["firstname", "type_id"]

        serializer = ScalarRelationPersonSerializer(
            data={"firstname": "Invalid source", "type_id": self.first_type.id}
        )

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "must validate to a PersonType instance or None",
        ):
            serializer.is_valid()

    def test_custom_type_input_field_override_updates_the_model_type(self) -> None:
        person = PersonFactory(person_type=self.first_type)
        serializer = TypeIdPersonSerializer(
            person,
            data={
                "type_id": self.second_type.id,
                "second_value": "updated",
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(person.person_type, self.second_type)
        self.assertTrue(
            person.custom_values.filter(
                field=self.second_field, value="updated"
            ).exists()
        )

    def test_custom_type_input_field_override_accepts_null(self) -> None:
        person = PersonFactory(person_type=self.first_type)
        serializer = TypeIdPersonSerializer(
            person,
            data={"type_id": None, "default_value": "default"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertIsNone(person.person_type)
        self.assertTrue(
            person.custom_values.filter(
                field=self.default_field, value="default"
            ).exists()
        )

    def test_custom_type_input_field_must_persist_the_model_type(self) -> None:
        class InvalidTypeAliasSerializer(TypeAwarePersonSerializer):
            custom_field_type_input_field = "type_id"
            type_id = serializers.IntegerField(required=False)

            class Meta:
                model = Person
                fields = ["firstname", "type_id"]

        serializer = InvalidTypeAliasSerializer(
            data={"firstname": "Invalid", "type_id": self.first_type.id}
        )

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "must map to 'person_type' or 'person_type_id'",
        ):
            serializer.is_valid()

    def test_custom_type_input_field_must_be_declared(self) -> None:
        class MissingTypeAliasSerializer(TypeAwarePersonSerializer):
            custom_field_type_input_field = "missing_type_id"

        serializer = MissingTypeAliasSerializer(data={"firstname": "Invalid"})

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "missing_type_id must be declared in the serializer fields",
        ):
            serializer.is_valid()

    def test_undeclared_type_input_cannot_authorize_typed_custom_fields(self) -> None:
        serializer = PersonSerializer(
            data={
                "firstname": "Undeclared",
                "person_type": self.second_type.id,
                "second_value": "tampered",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("second_value", serializer.errors)

    def test_read_only_type_input_cannot_authorize_typed_custom_fields(self) -> None:
        class ReadOnlyTypeSerializer(TypeAwarePersonSerializer):
            person_type = serializers.PrimaryKeyRelatedField(read_only=True)

        person = PersonFactory(person_type=self.first_type)
        serializer = ReadOnlyTypeSerializer(
            person,
            data={
                "person_type": self.second_type.id,
                "second_value": "tampered",
            },
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("second_value", serializer.errors)
        self.assertEqual(person.person_type, self.first_type)
        self.assertFalse(person.custom_values.filter(field=self.second_field).exists())

    def test_object_validation_cannot_change_the_selected_type(self) -> None:
        class RewritingTypeSerializer(TypeAwarePersonSerializer):
            def validate(self, attrs: dict) -> dict:
                attrs["person_type"] = self.context["replacement_type"]
                return attrs

        serializer = RewritingTypeSerializer(
            data={
                "firstname": "Rewritten",
                "person_type": self.first_type.id,
                "first_value": "must not be saved for another type",
            },
            context={"replacement_type": self.second_type},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("person_type", serializer.errors)
        self.assertFalse(Person.objects.filter(firstname="Rewritten").exists())

    def test_serialization_and_update_use_instance_type_when_input_omits_it(
        self,
    ) -> None:
        person = PersonFactory(person_type=self.first_type)

        output = TypeAwarePersonSerializer(person)
        update = TypeAwarePersonSerializer(
            person, data={"first_value": "updated"}, partial=True
        )

        self.assertIn("first_value", output.fields)
        self.assertNotIn("second_value", output.fields)
        self.assertTrue(update.is_valid(), update.errors)
        update.save()

    def test_type_selector_default_is_used_on_create(self) -> None:
        default_type = self.first_type
        calls: list[PersonType] = []

        def get_default_type() -> PersonType:
            calls.append(default_type)
            return default_type

        class DefaultTypePersonSerializer(TypeAwarePersonSerializer):
            person_type = serializers.PrimaryKeyRelatedField(
                default=get_default_type,
                queryset=PersonType.objects.all(),
                required=False,
            )

        serializer = DefaultTypePersonSerializer(
            data={"firstname": "Default", "first_value": "typed"}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(person.custom_values.filter(field=self.first_field).exists())
        self.assertEqual(calls, [self.first_type])

    def test_hidden_type_selector_default_is_used_on_create(self) -> None:
        default_type = self.first_type
        calls: list[tuple[PersonType, str]] = []

        def get_default_type(serializer_field: serializers.Field) -> PersonType:
            selected_type = serializer_field.context["default_type"]
            calls.append((selected_type, serializer_field.field_name))
            return selected_type

        setattr(get_default_type, "requires_context", True)

        class HiddenDefaultTypePersonSerializer(TypeAwarePersonSerializer):
            person_type = serializers.HiddenField(default=get_default_type)

        serializer = HiddenDefaultTypePersonSerializer(
            data={
                "firstname": "Hidden default",
                "person_type": self.second_type.pk,
                "first_value": "typed",
            },
            context={"default_type": default_type},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(person.custom_values.filter(field=self.first_field).exists())
        self.assertEqual(calls, [(self.first_type, "person_type")])

    def test_context_type_selector_default_can_read_static_parent_fields(self) -> None:
        calls: list[set[str]] = []

        def get_default_type(serializer_field: serializers.Field) -> PersonType:
            calls.append(set(serializer_field.parent.fields))
            return self.first_type

        setattr(get_default_type, "requires_context", True)

        class ParentFieldsDefaultTypePersonSerializer(TypeAwarePersonSerializer):
            person_type = serializers.PrimaryKeyRelatedField(
                default=get_default_type,
                queryset=PersonType.objects.all(),
                required=False,
            )

        serializer = ParentFieldsDefaultTypePersonSerializer(
            data={"firstname": "Static siblings", "first_value": "typed"}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(
            calls,
            [{"email", "firstname", "lastname", "person_type"}],
        )
        self.assertIs(serializer.fields["firstname"].parent, serializer)
        self.assertIn("first_value", serializer.fields)
        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(person.custom_values.filter(field=self.first_field).exists())

    def test_type_selector_default_is_used_on_full_update(self) -> None:
        default_type = self.second_type
        calls: list[PersonType] = []

        def get_default_type() -> PersonType:
            calls.append(default_type)
            return default_type

        class DefaultTypePersonSerializer(TypeAwarePersonSerializer):
            person_type = serializers.PrimaryKeyRelatedField(
                default=get_default_type,
                queryset=PersonType.objects.all(),
                required=False,
            )

        person = PersonFactory(person_type=self.first_type)
        serializer = DefaultTypePersonSerializer(
            person,
            data={"firstname": "Full update", "second_value": "typed"},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(person.person_type, self.second_type)
        self.assertTrue(person.custom_values.filter(field=self.second_field).exists())
        self.assertEqual(calls, [self.second_type])

    def test_type_selector_default_is_skipped_on_partial_update(self) -> None:
        default_type = self.second_type
        calls: list[PersonType] = []

        def get_default_type() -> PersonType:
            calls.append(default_type)
            return default_type

        class DefaultTypePersonSerializer(TypeAwarePersonSerializer):
            person_type = serializers.PrimaryKeyRelatedField(
                default=get_default_type,
                queryset=PersonType.objects.all(),
                required=False,
            )

        person = PersonFactory(person_type=self.first_type)
        serializer = DefaultTypePersonSerializer(
            person,
            data={"first_value": "typed"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(person.custom_values.filter(field=self.first_field).exists())
        self.assertEqual(calls, [])

    def test_create_only_type_selector_default_runs_once_only_on_create(self) -> None:
        default_type = self.first_type
        calls: list[PersonType] = []

        def get_default_type() -> PersonType:
            calls.append(default_type)
            return default_type

        class CreateOnlyDefaultTypePersonSerializer(TypeAwarePersonSerializer):
            person_type = serializers.PrimaryKeyRelatedField(
                default=serializers.CreateOnlyDefault(get_default_type),
                queryset=PersonType.objects.all(),
                required=False,
            )

        create = CreateOnlyDefaultTypePersonSerializer(
            data={"firstname": "Create only", "first_value": "created"}
        )

        self.assertTrue(create.is_valid(), create.errors)
        person = create.save()
        self.assertEqual(person.person_type, self.first_type)
        self.assertEqual(calls, [self.first_type])

        calls.clear()
        update = CreateOnlyDefaultTypePersonSerializer(
            person,
            data={"firstname": "Updated", "first_value": "updated"},
        )

        self.assertTrue(update.is_valid(), update.errors)
        person = update.save()
        self.assertEqual(person.person_type, self.first_type)
        self.assertEqual(calls, [])

    def test_type_selector_default_error_runs_once_and_preserves_code(self) -> None:
        calls: list[set[str]] = []

        def invalid_default(serializer_field: serializers.Field) -> PersonType:
            calls.append(set(serializer_field.parent.fields))
            raise serializers.ValidationError("Unavailable type", code="unavailable")

        setattr(invalid_default, "requires_context", True)

        class InvalidDefaultTypePersonSerializer(TypeAwarePersonSerializer):
            person_type = serializers.PrimaryKeyRelatedField(
                default=invalid_default,
                queryset=PersonType.objects.all(),
                required=False,
            )

        serializer = InvalidDefaultTypePersonSerializer(
            data={"firstname": "Invalid default"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["person_type"][0].code, "unavailable")
        self.assertEqual(
            calls,
            [{"email", "firstname", "lastname", "person_type"}],
        )
        self.assertIs(serializer.fields["firstname"].parent, serializer)

    def test_nullable_related_type_selector_normalizes_empty_string_to_none(
        self,
    ) -> None:
        serializer = TypeAwarePersonSerializer(
            data={
                "firstname": "No type",
                "person_type": "",
                "default_value": "global",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("first_value", serializer.fields)
        self.assertNotIn("second_value", serializer.fields)
        person = serializer.save()

        self.assertIsNone(person.person_type)
        self.assertTrue(person.custom_values.filter(field=self.default_field).exists())

    def test_many_callable_type_defaults_run_once_and_are_item_scoped(self) -> None:
        default_types = iter((self.first_type, self.second_type))
        calls: list[PersonType] = []

        def get_default_type() -> PersonType:
            default_type = next(default_types)
            calls.append(default_type)
            return default_type

        class DefaultTypePersonSerializer(TypeAwarePersonSerializer):
            person_type = serializers.PrimaryKeyRelatedField(
                default=get_default_type,
                queryset=PersonType.objects.all(),
                required=False,
            )

        serializer = DefaultTypePersonSerializer(
            data=[
                {"firstname": "First", "first_value": "first"},
                {"firstname": "Second", "second_value": "second"},
            ],
            many=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        first, second = serializer.save()

        self.assertEqual(calls, [self.first_type, self.second_type])
        self.assertEqual(first.person_type, self.first_type)
        self.assertEqual(second.person_type, self.second_type)
        self.assertTrue(first.custom_values.filter(field=self.first_field).exists())
        self.assertTrue(second.custom_values.filter(field=self.second_field).exists())

    def test_explicit_related_type_selector_conversion_is_replayed(self) -> None:
        serializer = TypeAwarePersonSerializer(
            data={
                "firstname": "One lookup",
                "person_type": self.first_type.pk,
                "first_value": "typed",
            }
        )

        # Field construction performs the one related-object lookup needed to
        # select dynamic fields. Normal validation replays that conversion.
        self.assertIn("first_value", serializer.fields)
        with self.assertNumQueries(0):
            is_valid = serializer.is_valid()

        self.assertTrue(is_valid, serializer.errors)

    def test_type_selector_conversion_can_read_static_parent_fields(self) -> None:
        calls: list[set[str]] = []

        class ParentFieldsPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
            def to_internal_value(self, data: Any) -> PersonType:
                calls.append(set(self.parent.fields))
                return super().to_internal_value(data)

        class ParentFieldsTypePersonSerializer(TypeAwarePersonSerializer):
            person_type = ParentFieldsPrimaryKeyRelatedField(
                queryset=PersonType.objects.all(),
                required=False,
            )

        serializer = ParentFieldsTypePersonSerializer(
            data={
                "firstname": "Conversion siblings",
                "person_type": self.first_type.pk,
                "first_value": "typed",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(
            calls,
            [{"email", "firstname", "lastname", "person_type"}],
        )
        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(person.custom_values.filter(field=self.first_field).exists())

    def test_object_validation_cannot_add_an_omitted_type_on_create(self) -> None:
        class AddingTypePersonSerializer(TypeAwarePersonSerializer):
            def validate(self, attrs: dict) -> dict:
                attrs["person_type"] = self.context["added_type"]
                return attrs

        serializer = AddingTypePersonSerializer(
            data={"firstname": "Added"},
            context={"added_type": self.first_type},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("person_type", serializer.errors)

    def test_object_validation_cannot_change_an_omitted_type_on_update(self) -> None:
        class AddingTypePersonSerializer(TypeAwarePersonSerializer):
            def validate(self, attrs: dict) -> dict:
                attrs["person_type"] = self.context["added_type"]
                return attrs

        person = PersonFactory(person_type=self.first_type)
        serializer = AddingTypePersonSerializer(
            person,
            data={"firstname": "Changed"},
            context={"added_type": self.second_type},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("person_type", serializer.errors)
        self.assertEqual(person.person_type, self.first_type)

    def test_many_serialization_uses_each_instance_type(self) -> None:
        first_person = PersonFactory(person_type=self.first_type)
        second_person = PersonFactory(person_type=self.second_type)
        first_person.refresh_with_custom_fields()
        second_person.refresh_with_custom_fields()
        first_person.first_value = "first"
        second_person.second_value = "second"
        first_person.save()
        second_person.save()

        data = TypeAwarePersonSerializer([first_person, second_person], many=True).data

        self.assertEqual(data[0]["first_value"], "first")
        self.assertNotIn("second_value", data[0])
        self.assertEqual(data[1]["second_value"], "second")
        self.assertNotIn("first_value", data[1])

    def test_many_serialization_caches_field_definitions_per_type(self) -> None:
        people = [PersonFactory(person_type=self.first_type) for _ in range(3)]
        for person in people:
            person.refresh_with_custom_fields()

        with self.assertNumQueries(2):
            data = TypeAwarePersonSerializer(people, many=True).data

        self.assertEqual(len(data), len(people))

    def test_many_serialization_queries_scale_with_distinct_types(self) -> None:
        people = [
            PersonFactory(
                person_type=self.first_type if index % 2 == 0 else self.second_type
            )
            for index in range(20)
        ]
        for person in people:
            person.refresh_with_custom_fields()

        # One identifier query plus one definition query for each distinct type.
        with self.assertNumQueries(3):
            data = TypeAwarePersonSerializer(people, many=True).data

        self.assertEqual(len(data), len(people))
        for index, item in enumerate(data):
            expected = "first_value" if index % 2 == 0 else "second_value"
            unexpected = "second_value" if index % 2 == 0 else "first_value"
            self.assertIn(expected, item)
            self.assertNotIn(unexpected, item)

    def test_many_serialization_does_not_resolve_choice_defaults(self) -> None:
        single = CustomFieldFactory(
            identifier="single_choice_default",
            choice_field=True,
        )
        single_choice = CustomValueFactory(field=single)
        single.default = single_choice.id
        single.save(update_fields=["default"])
        multiple = CustomFieldFactory(
            identifier="multiple_choice_default",
            choice_field=True,
            multiple=True,
        )
        first_choice = CustomValueFactory(field=multiple)
        second_choice = CustomValueFactory(field=multiple)
        multiple.default = [first_choice.id, second_choice.id]
        multiple.save(update_fields=["default"])
        people = [PersonFactory(person_type=self.first_type) for _ in range(3)]
        for person in people:
            person.refresh_with_custom_fields()

        with self.assertNumQueries(2):
            data = TypeAwarePersonSerializer(people, many=True).data

        self.assertEqual(len(data), len(people))

    def test_many_create_uses_each_submitted_type(self) -> None:
        first_default = CustomFieldFactory(
            identifier="first_default",
            type_content_type=self.type_ct,
            type_id=self.first_type.id,
            default="default",
        )
        serializer = TypeAwarePersonSerializer(
            data=[
                {
                    "firstname": "First",
                    "person_type": self.first_type.id,
                    "first_value": "first",
                },
                {
                    "firstname": "Second",
                    "person_type": self.second_type.id,
                    "second_value": "second",
                },
            ],
            many=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        first_person, second_person = serializer.save()

        self.assertEqual(serializer.data[0]["first_value"], "first")
        self.assertNotIn("second_value", serializer.data[0])
        self.assertEqual(serializer.data[1]["second_value"], "second")
        self.assertNotIn("first_value", serializer.data[1])

        first_person.refresh_with_custom_fields()
        second_person.refresh_with_custom_fields()

        self.assertEqual(first_person.first_value, "first")
        self.assertEqual(first_person.first_default, first_default.default)
        self.assertEqual(second_person.second_value, "second")

    def test_mapping_create_ignores_configured_fields_for_other_types(self) -> None:
        serializer = TypeAwarePersonMappingSerializer(
            data={
                "external_firstname": "First",
                "external_type": self.first_type.id,
                "external_first": "first",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(
            person.custom_values.filter(
                field=self.first_field,
                value="first",
            ).exists()
        )

    def test_mapping_context_type_default_reads_mapped_static_fields(self) -> None:
        calls: list[set[str]] = []

        def get_default_type(serializer_field: serializers.Field) -> PersonType:
            calls.append(set(serializer_field.parent.fields))
            return self.first_type

        setattr(get_default_type, "requires_context", True)

        class ParentFieldsDefaultMappingSerializer(TypeAwarePersonMappingSerializer):
            person_type = serializers.PrimaryKeyRelatedField(
                default=get_default_type,
                queryset=PersonType.objects.all(),
                required=False,
            )

        serializer = ParentFieldsDefaultMappingSerializer(
            data={
                "external_firstname": "Mapped default",
                "external_first": "typed",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(calls, [{"firstname", "person_type"}])
        self.assertEqual(person.person_type, self.first_type)
        self.assertTrue(person.custom_values.filter(field=self.first_field).exists())

    def test_many_mapping_create_uses_each_submitted_type(self) -> None:
        data = [
            {
                "external_firstname": "First",
                "external_type": self.first_type.id,
                "external_first": "first",
            },
            {
                "external_firstname": "Second",
                "external_type": self.second_type.id,
                "external_second": "second",
            },
            {
                "external_firstname": "Default",
                "external_default": "default",
            },
        ]
        serializer = TypeAwarePersonMappingSerializer(data=data, many=True)

        self.assertEqual(
            serializer.initial_data,
            [
                {
                    "firstname": "First",
                    "person_type": self.first_type.id,
                    "first_value": "first",
                },
                {
                    "firstname": "Second",
                    "person_type": self.second_type.id,
                    "second_value": "second",
                },
                {
                    "firstname": "Default",
                    "default_value": "default",
                },
            ],
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        first, second, default = serializer.save()

        self.assertEqual(first.person_type, self.first_type)
        self.assertEqual(second.person_type, self.second_type)
        self.assertIsNone(default.person_type)
        self.assertTrue(first.custom_values.filter(field=self.first_field).exists())
        self.assertTrue(second.custom_values.filter(field=self.second_field).exists())
        self.assertTrue(default.custom_values.filter(field=self.default_field).exists())

    def test_mapping_excludes_custom_fields_without_affecting_model_fields(
        self,
    ) -> None:
        serializer = TypeAwarePersonMappingSerializer(
            data={
                "external_firstname": "Mapped",
                "external_type": self.first_type.id,
                "external_default": "ignored default",
                "external_first": "ignored typed",
            },
            exclude_custom_fields=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        person = serializer.save()

        self.assertEqual(person.firstname, "Mapped")
        self.assertEqual(person.person_type, self.first_type)
        self.assertFalse(person.custom_values.exists())
        self.assertNotIn("default_value", serializer.fields)
        self.assertNotIn("first_value", serializer.fields)

    def test_mapping_does_not_run_hooks_for_excluded_custom_fields(self) -> None:
        calls: list[str] = []

        class FormattingMappingSerializer(TypeAwarePersonMappingSerializer):
            def format_first_value(self, value: str) -> str:
                calls.append(value)
                return value

        serializer = FormattingMappingSerializer(
            data={
                "external_firstname": "Mapped",
                "external_type": self.first_type.id,
                "external_first": "ignored",
            },
            exclude_custom_fields=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(calls, [])

    def test_many_mapping_excludes_custom_fields_per_item(self) -> None:
        serializer = TypeAwarePersonMappingSerializer(
            data=[
                {
                    "external_firstname": "First",
                    "external_type": self.first_type.id,
                    "external_first": "ignored",
                },
                {
                    "external_firstname": "Second",
                    "external_type": self.second_type.id,
                    "external_second": "ignored",
                },
            ],
            many=True,
            exclude_custom_fields=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        first, second = serializer.save()

        self.assertEqual(first.firstname, "First")
        self.assertEqual(second.firstname, "Second")
        self.assertFalse(first.custom_values.exists())
        self.assertFalse(second.custom_values.exists())

    def test_many_mapping_rejects_field_for_another_type_per_item(self) -> None:
        serializer = TypeAwarePersonMappingSerializer(
            data=[
                {
                    "external_firstname": "Wrong",
                    "external_type": self.first_type.id,
                    "external_second": "wrong",
                },
                {
                    "external_firstname": "Second",
                    "external_type": self.second_type.id,
                    "external_second": "second",
                },
            ],
            many=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("second_value", serializer.errors[0])
        self.assertEqual(serializer.errors[1], {})

    def test_many_mapping_preserves_invalid_selector_error_per_item(self) -> None:
        serializer = TypeAwarePersonMappingSerializer(
            data=[
                {
                    "external_firstname": "Missing",
                    "external_type": 999_999,
                    "external_first": "must not be accepted",
                },
                {
                    "external_firstname": "First",
                    "external_type": self.first_type.id,
                    "external_first": "first",
                },
            ],
            many=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors[0]["person_type"][0].code, "does_not_exist")
        self.assertEqual(serializer.errors[1], {})

    def test_many_create_accepts_slug_type_selectors(self) -> None:
        serializer = SlugTypePersonSerializer(
            data=[
                {
                    "firstname": "First",
                    "person_type": self.first_type.title,
                    "first_value": "first",
                },
                {
                    "firstname": "Second",
                    "person_type": self.second_type.title,
                    "second_value": "second",
                },
            ],
            many=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        first_person, second_person = serializer.save()

        self.assertEqual(first_person.person_type, self.first_type)
        self.assertEqual(second_person.person_type, self.second_type)
        self.assertTrue(
            first_person.custom_values.filter(field=self.first_field).exists()
        )
        self.assertTrue(
            second_person.custom_values.filter(field=self.second_field).exists()
        )

    def test_many_validated_data_representation_uses_each_submitted_type(
        self,
    ) -> None:
        serializer = TypeAwarePersonSerializer(
            data=[
                {
                    "firstname": "First",
                    "person_type": self.first_type.id,
                    "first_value": "first",
                },
                {
                    "firstname": "Second",
                    "person_type": self.second_type.id,
                    "second_value": "second",
                },
            ],
            many=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertEqual(serializer.data[0]["first_value"], "first")
        self.assertNotIn("second_value", serializer.data[0])
        self.assertEqual(serializer.data[1]["second_value"], "second")
        self.assertNotIn("first_value", serializer.data[1])

    def test_many_rejects_non_list_input(self) -> None:
        serializer = TypeAwarePersonSerializer(data={}, many=True)

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["non_field_errors"][0].code, "not_a_list")

    def test_many_respects_allow_empty(self) -> None:
        serializer = TypeAwarePersonSerializer(data=[], many=True, allow_empty=False)

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["non_field_errors"][0].code, "empty")

    def test_many_respects_minimum_and_maximum_length(self) -> None:
        too_short = TypeAwarePersonSerializer(
            data=[],
            many=True,
            min_length=1,
        )
        too_long = TypeAwarePersonSerializer(
            data=[{"firstname": "First"}, {"firstname": "Second"}],
            many=True,
            max_length=1,
        )

        self.assertFalse(too_short.is_valid())
        self.assertEqual(
            too_short.errors["non_field_errors"][0].code,
            "min_length",
        )
        self.assertFalse(too_long.is_valid())
        self.assertEqual(
            too_long.errors["non_field_errors"][0].code,
            "max_length",
        )

    def test_many_validation_reports_errors_for_the_correct_item(self) -> None:
        serializer = TypeAwarePersonSerializer(
            data=[
                {
                    "firstname": "First",
                    "person_type": self.first_type.id,
                    "first_value": "first",
                },
                {
                    "firstname": "Second",
                    "person_type": self.second_type.id,
                    "first_value": "wrong type",
                },
            ],
            many=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors[0], {})
        self.assertIn("first_value", serializer.errors[1])

    def test_update_uses_submitted_type_change(self) -> None:
        person = PersonFactory(person_type=self.first_type)
        serializer = TypeAwarePersonSerializer(
            person,
            data={
                "person_type": self.second_type.id,
                "second_value": "new type value",
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("first_value", serializer.fields)
        person = serializer.save()
        self.assertEqual(person.person_type, self.second_type)

    def test_type_change_retains_but_hides_values_from_the_previous_type(
        self,
    ) -> None:
        person = PersonFactory(person_type=self.first_type)
        initial = TypeAwarePersonSerializer(
            person,
            data={"first_value": "retained"},
            partial=True,
        )
        self.assertTrue(initial.is_valid(), initial.errors)
        initial.save()

        change = TypeAwarePersonSerializer(
            person,
            data={"person_type": self.second_type.id},
            partial=True,
        )
        self.assertTrue(change.is_valid(), change.errors)
        person = change.save()

        self.assertTrue(
            person.custom_values.filter(
                field=self.first_field, value="retained"
            ).exists()
        )
        self.assertNotIn("first_value", TypeAwarePersonSerializer(person).data)

        forbidden_update = TypeAwarePersonSerializer(
            person,
            data={"first_value": "changed"},
            partial=True,
        )
        self.assertFalse(forbidden_update.is_valid())
        self.assertIn("first_value", forbidden_update.errors)

    def test_missing_type_includes_default_fields_only(self) -> None:
        serializer = TypeAwarePersonSerializer(data={"firstname": "No type"})

        self.assertIn("default_value", serializer.fields)
        self.assertNotIn("first_value", serializer.fields)
        self.assertNotIn("second_value", serializer.fields)

    def test_nonexistent_type_is_rejected_by_model_field(self) -> None:
        serializer = TypeAwarePersonSerializer(
            data={"firstname": "Missing", "person_type": 999_999}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("person_type", serializer.errors)

    def test_field_for_another_type_is_rejected_instead_of_ignored(self) -> None:
        serializer = TypeAwarePersonSerializer(
            data={
                "firstname": "Wrong",
                "person_type": self.first_type.id,
                "second_value": "tampered",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("second_value", serializer.errors)

    def test_field_with_mismatched_type_content_type_is_rejected(self) -> None:
        wrong_field = CustomFieldFactory(
            identifier="wrong_content_type",
            type_content_type=ContentType.objects.get_for_model(Municipality),
            type_id=self.first_type.id,
        )
        serializer = TypeAwarePersonSerializer(
            data={
                "firstname": "Wrong",
                "person_type": self.first_type.id,
                wrong_field.identifier: "tampered",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn(wrong_field.identifier, serializer.errors)
