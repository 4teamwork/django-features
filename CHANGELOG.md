
2025.5.14 (2025-10-30)
----------------------

Other changes:

- Provide the unmapped data data in the mapping serializer. [TI-2994](https://4teamwork.atlassian.net/browse/TI-2994>)


2025.5.13 (2025-10-30)
----------------------

Bug fixes:

- Fixes AttributeError when overriding the init function of the CustomFieldBaseModelSerializer because of the params. (`TI-2994 <https://4teamwork.atlassian.net/browse/TI-2994>`_)


2025.5.12 (2025-10-27)
----------------------

No changes.


2025.5.11 (2025-10-27)
----------------------

No changes.


2025.5.10 (2025-10-27)
----------------------

Bug fixes:

- Array custom fields get annotated correctly.


2025.5.9 (2025-10-24)
---------------------

No changes.


2025.8.0 (2025-10-24)
---------------------

No changes.


2025.5.8 (2025-10-24)
---------------------

Bug fixes:

- (`master <https://4teamwork.atlassian.net/browse/master>`_)


2025.5.6 (2025-10-24)
---------------------

Bug fixes:

- Handle None values when setting custom values. (`master <https://4teamwork.atlassian.net/browse/master>`_)


2025.5.5 (2025-10-23)
---------------------

No changes.


2025.5.4 (2025-10-23)
---------------------

No changes.


2025.5.3 (2025-10-23)
---------------------

No changes.


2025.5.2 (2025-10-23)
---------------------

No changes.


2025.5.1 (2025-10-23)
---------------------

No changes.


2025.5.0 (2025-10-23)
---------------------

Other changes:

- Improve MappingSerializer and add option for more related fields. (`TI-2893 <https://4teamwork.atlassian.net/browse/TI-2893>`_)


2025.4.3 (2025-10-22)
---------------------

No changes.


2025.3.0 (2025-10-22)
---------------------

No changes.


2025.4.2 (2025-10-22)
---------------------

No changes.


2025.4.1 (2025-10-22)
---------------------

No changes.


2025.4.0 (2025-10-22)
---------------------

New features:

- Add new custom fields feature. (`TI-2893 <https://4teamwork.atlassian.net/browse/TI-2893>`_)
- Implements the MappingValidationMixin to validate nested field mappings and MappingSerializer to import models with nested mapping. (`TI-2893 <https://4teamwork.atlassian.net/browse/TI-2893>`_)


2025.3.1 (2025-10-10)
---------------------

Other changes:

- [system_message]: Fix empty relation for dismissed users and handle unauthorized queryset filters. (`TI-2893 <https://4teamwork.atlassian.net/browse/TI-2893>`_)


2025.3.0 (2025-09-10)
---------------------

New features:

- The page and page size query params are now configurable. (`TI-2887 <https://4teamwork.atlassian.net/browse/TI-2887>`_)


2025.2.0 (2025-09-09)
---------------------

Bug fixes:

- Make the dismiss endpoint more flexible by adding optional args and kwargs params. (`TI-2887 <https://4teamwork.atlassian.net/browse/TI-2887>`_)


2025.1.2 (2025-09-04)
---------------------

Other changes:

- Use BigAutoField as auto field. (`TI-2887 <https://4teamwork.atlassian.net/browse/TI-2887>`_)


2025.1.1 (2025-09-04)
---------------------

Bug fixes:

- Default system message type names fixed. (`TI-2887 <https://4teamwork.atlassian.net/browse/TI-2887>`_)


2025.1.0 (2025-09-04)
---------------------

New features:

- The system messages feature has been introduced. (`TI-2887 <https://4teamwork.atlassian.net/browse/TI-2887>`_)
