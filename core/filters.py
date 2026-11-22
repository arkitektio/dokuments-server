import strawberry
import strawberry_django
from django.contrib.postgres.search import SearchQuery
from django.db.models import QuerySet
from kante.types import Info
from strawberry import auto
from strawberry_django.filters import FilterLookup

from core import models


@strawberry.input
class IDFilterMixin:
    ids: list[strawberry.ID] | None

    def filter_ids(self, queryset: QuerySet, info: Info) -> QuerySet:
        if self.ids is None:
            return queryset
        return queryset.filter(id__in=self.ids)


@strawberry.input
class SearchFilterMixin:
    search: str | None

    def filter_search(self, queryset: QuerySet, info: Info) -> QuerySet:
        if self.search is None:
            return queryset
        return queryset.filter(name__contains=self.search)


@strawberry_django.filter(models.Dataset)
class DatasetFilter:
    id: auto
    name: FilterLookup[str] | None


@strawberry_django.filter(models.File)
class FileFilter(IDFilterMixin, SearchFilterMixin):
    id: auto
    name: FilterLookup[str] | None


@strawberry_django.filter(models.Document)
class DocumentFilter(IDFilterMixin):
    id: auto
    search: str | None

    def filter_search(self, queryset: QuerySet, info: Info) -> QuerySet:
        """A case-insensitive substring of the title: a document has a title, not a name."""
        if self.search is None:
            return queryset
        return queryset.filter(title__icontains=self.search)


@strawberry_django.filter(models.Page)
class PageFilter(IDFilterMixin):
    id: auto
    search: str | None

    def filter_search(self, queryset: QuerySet, info: Info) -> QuerySet:
        if self.search is None:
            return queryset
        return queryset.filter(content__search=SearchQuery(self.search))
