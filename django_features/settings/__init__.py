from configurations import Configuration
from configurations import values


class BaseConfiguration(Configuration):
    PAGE_QUERY_PARAM = values.Value("page")
    PAGE_SIZE_QUERY_PARAM = values.Value("page_size")
