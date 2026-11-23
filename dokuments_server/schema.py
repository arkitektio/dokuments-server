from typing import Annotated, Any

import strawberry
import strawberry_django
from arkitekt_datalayer import mutations as datalayer_mutations
from arkitekt_datalayer import scalars as datalayer_scalars
from arkitekt_datalayer.datalayer import load_config
from arkitekt_service.collaborations import graphql as collaboration_types
from arkitekt_service.graphql import (
    CollaborationGate,
    TelemetryExtension,
    annotate_schema,
)
from authentikate.strawberry import AuthExtension, AuthSubscribeExtension
from authentikate.strawberry.extension import AuthentikateExtension
from kante.types import Info
from koherent.strawberry.extension import KoherentExtension
from strawberry import ID as StrawberryID
from strawberry.schema.config import StrawberryConfig
from strawberry_django.optimizer import DjangoOptimizerExtension

from core import access, models, mutations, scoping, subscriptions, types
from dokuments_server.contract import EDITOR
from dokuments_server.logs import QuietErrorsSchema
from dokuments_server.service import service as dokuments_service

ID = Annotated[
    StrawberryID, strawberry.argument(description="The unique identifier of an object")
]


def field(scope: str = "dokuments_read", **kwargs: Any) -> Any:  # noqa: ANN401 - as strawberry_django's: the value of `x: T = field()`
    "A field an app needs ``scope`` for (``dokuments_read``, unless it says otherwise)."
    return strawberry_django.field(extensions=[AuthExtension(scopes=[scope])], **kwargs)


def mutation(
    scope: str = "dokuments_write", roles: list[str] | None = None, **kwargs: Any
) -> Any:  # noqa: ANN401 - as strawberry_django's: the value of `x: T = field()`
    """A write: an app needs ``scope`` for it, a member one of ``roles`` (``dokuments_editor`` unless it
    says otherwise; ``dokuments_admin`` holds every role)."""
    return strawberry_django.mutation(
        extensions=[AuthExtension(scopes=[scope], any_role_of=roles or [EDITOR])],
        **kwargs,
    )


def access_mutation(guests: bool = False, **kwargs: Any) -> Any:  # noqa: ANN401 - as strawberry_django's: the value of `x: T = field()`
    """A mutation that hands out read credentials: a read, for whoever may see what it reads.

    ``guests`` lets guests of the organization in: the resolver then finds only what is in their
    collaborations. Every other one refuses a guest (authentikate's ``SCOPED_READ_ONLY``)."""
    return strawberry_django.mutation(
        extensions=[AuthExtension(scopes=["dokuments_read"], allow_scoped=guests)],
        **kwargs,
    )


#: The collaborations of dokuments' files, which a guest of the organization is granted.
collaboration_api = collaboration_types.resolvers(
    fetch=lambda model, id, info: scoping.get_for_org(model, info, id)
)


def subscription(**kwargs: Any) -> Any:  # noqa: ANN401 - as strawberry_django's: the value of `x: T = field()`
    """A subscription: what it streams is read, so an app needs ``dokuments_read`` for it."""
    return strawberry.subscription(
        extensions=[AuthSubscribeExtension(scopes=["dokuments_read"])], **kwargs
    )


@strawberry.type
class Query:
    files: list[types.File] = field()
    documents: list[types.Document] = field()
    pages: list[types.Page] = field()

    @field(permission_classes=[])
    def file(self, info: Info, id: ID) -> types.File:
        return scoping.get_for_org(models.File, info, id)

    @field(permission_classes=[])
    def document(self, info: Info, id: ID) -> types.Document:
        return scoping.get_for_org(models.Document, info, id)

    @field(permission_classes=[])
    def page(self, info: Info, id: ID) -> types.Page:
        return scoping.get_for_org(models.Page, info, id)

    collaborations: list[collaboration_types.Collaboration] = field(
        resolver=collaboration_api.collaborations,
        description="List the organization's collaborations that hold something of dokuments (a guest: the collaborations granted to them)",
    )
    collaboration: collaboration_types.Collaboration = field(
        resolver=collaboration_api.collaboration,
        description="Get a single collaboration by its key (lok's): what was put in it here",
    )
    collaborations_stats: collaboration_types.CollaborationStats = field(
        resolver=collaboration_api.collaborations_stats,
        description="Count the collaborations `collaborations` lists, and the objects in them",
    )


def upload_mutation(**kwargs: Any) -> Any:  # noqa: ANN401 - as strawberry_django's: the value of `x: T = field()`
    """A mutation that hands out or finishes upload credentials: an app needs ``dokuments_write`` for it,
    a member one of ``datalayer.upload_roles`` (``dokuments_editor`` when none are configured)."""
    roles = load_config().upload_roles or [EDITOR]
    return strawberry_django.mutation(
        extensions=[AuthExtension(scopes=["dokuments_write"], any_role_of=roles)],
        **kwargs,
    )


@strawberry.type
class Mutation:
    # Uploads (arkitekt_datalayer): request a grant, write the file to S3, finish, then file it.
    request_media_upload = upload_mutation(
        resolver=datalayer_mutations.request_media_upload,
        description="Request temporary S3 credentials to upload one file (a document, or a page's image).",
    )
    finish_media_upload = upload_mutation(
        resolver=datalayer_mutations.finish_media_upload,
        description="Finalize an upload after the client has written the object.",
    )
    refresh_media_upload = upload_mutation(
        description="Reissue upload credentials for a media upload still in flight, to the same key, so a write that outlives its credentials carries on. Only the uploader may, never for a finished store, and never past the upload's time limit",
        resolver=datalayer_mutations.refresh_media_upload,
    )
    request_media_access = access_mutation(
        guests=True,
        resolver=access.request_media_access,
        description="Request temporary S3 read credentials for an uploaded file (a file's bytes, or a page's image). A guest of the organization gets them only for what is in one of their collaborations.",
    )
    request_general_media_access = access_mutation(
        resolver=datalayer_mutations.request_general_media_access,
        description="Request temporary S3 read credentials for the organization's files.",
    )

    # File
    from_file_like = mutation(
        resolver=mutations.from_file_like,
        description="Create a file from file-like data",
    )
    delete_file = mutation(
        resolver=mutations.delete_file, description="Delete an existing file"
    )

    # Experiment
    create_document = mutation(
        resolver=mutations.create_document, description="Create a new document"
    )

    # Page
    create_page = mutation(
        resolver=mutations.create_page, description="Create a new page in a document"
    )

    # --- Collaborations ----------------------------------------------------
    add_to_collaboration = mutation(
        scope="dokuments_share",
        resolver=collaboration_api.add_to_collaboration,
        description="Put a file in a collaboration (lok's, by its key), with its bytes and its pages' images: its documents and their pages are in it with it. The collaboration's row here is made the first time something is put in",
    )
    add_many_to_collaboration = mutation(
        scope="dokuments_share",
        resolver=collaboration_api.add_many_to_collaboration,
        description="Put several files in a collaboration (by its key) at once, each with what it needs to be seen: all of them, or none",
    )
    share_workflow = mutation(
        scope="dokuments_share",
        resolver=collaboration_api.share_workflow,
        description="Put what a workflow (its root task) created in dokuments in a collaboration, as it is now: what it makes later is not. A document or page made in the workflow for a file made before it, and not shared, is left out and reported; `dryRun` only says what would be put in",
    )
    remove_from_collaboration = mutation(
        scope="dokuments_share",
        resolver=collaboration_api.remove_from_collaboration,
        description="Take a file out of a collaboration, with what it brought that nothing else there needs",
    )
    delete_collaboration = mutation(
        scope="dokuments_share",
        resolver=collaboration_api.delete_collaboration,
        description="Take everything dokuments put in a collaboration (by its key) out of it: whoever was granted it sees nothing of it here any more. lok's collaboration, and its grants, stay",
    )


@strawberry.type
class Subscription:
    """The root subscription type"""

    files = subscription(
        resolver=subscriptions.files, description="Subscribe to real-time file updates"
    )


# A federation schema: the datalayer's store types are federated entities carrying ``@key``.
class Schema(QuietErrorsSchema, strawberry.federation.Schema):
    """strawberry.federation.Schema, logging expected resolver errors as one line and bugs with a traceback (see logs.py)."""


schema = Schema(
    query=Query,
    subscription=Subscription,
    mutation=Mutation,
    extensions=[
        TelemetryExtension,
        AuthentikateExtension,
        # A guest of the organization is handed only what is in their collaborations.
        CollaborationGate,
        KoherentExtension,
        DjangoOptimizerExtension,
    ],
    config=StrawberryConfig(scalar_map={**datalayer_scalars.SCALAR_MAP}),
    types=[],
)

# Which structure each type is (`@identified`), what stands for every scope and role here
# (`dokuments_all`, `dokuments_admin`), and, behind the gate, that dokuments lets guests in.
annotate_schema(schema, dokuments_service)
