"""Every read of dokuments' models, held to the caller's organization and, for a guest, to their collaborations.

The types' ``get_queryset`` (root lists, single fetches and nested relations alike) and the root
fields that fetch one object by id all go through :func:`scope_queryset`. At a root field, a guest of
the organization is narrowed to what is in their collaborations (``object_scope``); below one, the
collaboration gate (``arkitekt_service.graphql.CollaborationGate``) holds them to it.
"""

from typing import TypeVar

from arkitekt_service.collaborations.guests import object_scope
from django.db.models import Model, QuerySet
from kante.types import Info

from core import models

_M = TypeVar("_M", bound=Model)

#: The lookup from each model read here to the organization it belongs to.
ORGANIZATION_PATHS: dict[type[Model], str] = {
    models.File: "organization",
    models.Document: "file__organization",
    models.Page: "document__file__organization",
}


def scope_queryset(queryset: QuerySet[_M], info: Info) -> QuerySet[_M]:
    """``queryset``, narrowed to the request's organization, and at a root field, for a guest, to
    what is in their collaborations."""
    path = ORGANIZATION_PATHS[queryset.model]
    return object_scope(
        queryset.filter(**{path: info.context.request.organization}), info=info
    )


def get_for_org(model: type[_M], info: Info, id: object) -> _M:
    """``model``'s row ``id``, if the caller may read it (a ``DoesNotExist`` otherwise)."""
    return scope_queryset(model._default_manager.all(), info).get(pk=id)
