from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response


class NexusCursorPagination(CursorPagination):
    page_size = 50
    max_page_size = 500
    ordering = "-created_at"
    cursor_query_param = "cursor"

    def get_paginated_response(self, data):
        return Response({
            "count": None,  # cursor pagination doesn't count
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })


class NexusPagePagination(PageNumberPagination):
    page_size = 50
    max_page_size = 500
    page_query_param = "page"
    page_size_query_param = "limit"

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })
