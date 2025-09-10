from django.conf import settings
from rest_framework.pagination import PageNumberPagination


class PageNumberPaginator(PageNumberPagination):
    page_query_param = settings.PAGE_QUERY_PARAM
    page_size_query_param = settings.PAGE_SIZE_QUERY_PARAM
