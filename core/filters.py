import strawberry
from core import models
from strawberry import auto
from typing import Optional
from strawberry_django.filters import FilterLookup
import strawberry_django
from django.contrib.postgres.search import SearchQuery


@strawberry.input
class IDFilterMixin:
    ids: list[strawberry.ID] | None

    def filter_ids(self, queryset, info):
        if self.ids is None:
            return queryset
        return queryset.filter(id__in=self.ids)


@strawberry.input
class SearchFilterMixin:
    search: str | None

    def filter_search(self, queryset, info):
        if self.search is None:
            return queryset
        return queryset.filter(name__contains=self.search)


@strawberry_django.filter(models.Dataset)
class DatasetFilter:
    id: auto
    name: Optional[FilterLookup[str]]


@strawberry_django.filter(models.File)
class FileFilter(IDFilterMixin, SearchFilterMixin):
    id: auto
    name: Optional[FilterLookup[str]]


@strawberry_django.filter(models.Document)
class DocumentFilter(IDFilterMixin):
    id: auto
    search: str | None

    def filter_search(self, queryset, info):
        """A case-insensitive substring of the title: a document has a title, not a name."""
        if self.search is None:
            return queryset
        return queryset.filter(title__icontains=self.search)


@strawberry_django.filter(models.Page)
class PageFilter(IDFilterMixin):
    id: auto
    search: str | None

    def filter_search(self, queryset, info):
        if self.search is None:
            return queryset
        return queryset.filter(content__search=SearchQuery(self.search))
