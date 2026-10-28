from kante.types import Info
from dokuments_server.logs import QuietErrorsSchema
import strawberry

from arkitekt_datalayer import mutations as datalayer_mutations
from arkitekt_datalayer import scalars as datalayer_scalars
from arkitekt_datalayer.datalayer import load_config
from authentikate.strawberry import AuthExtension, AuthSubscribeExtension
from strawberry.schema.config import StrawberryConfig
from strawberry import ID as StrawberryID
from core import types, models
from core import mutations
from core import subscriptions
import strawberry_django
from koherent.strawberry.extension import KoherentExtension
from typing import Annotated
from authentikate.strawberry.extension import AuthentikateExtension
from strawberry_django.optimizer import DjangoOptimizerExtension
from authentikate.catch_alls import declare_catch_alls
from dokuments_server.contract import EDITOR, contract


ID = Annotated[StrawberryID, strawberry.argument(description="The unique identifier of an object")]


def field(scope: str = "dokuments_read", **kwargs):  # noqa: ANN003, ANN201
    "A field an app needs ``scope`` for (``dokuments_read``, unless it says otherwise)."
    return strawberry_django.field(extensions=[AuthExtension(scopes=[scope])], **kwargs)


def mutation(scope: str = "dokuments_write", roles: list[str] | None = None, **kwargs):  # noqa: ANN003, ANN201
    """A write: an app needs ``scope`` for it, a member one of ``roles`` (``dokuments_editor`` unless it
    says otherwise; ``dokuments_admin`` holds every role)."""
    return strawberry_django.mutation(extensions=[AuthExtension(scopes=[scope], any_role_of=roles or [EDITOR])], **kwargs)


def access_mutation(**kwargs):  # noqa: ANN003, ANN201
    """A mutation that hands out read credentials: a read, for whoever may see what it reads."""
    return strawberry_django.mutation(extensions=[AuthExtension(scopes=["dokuments_read"])], **kwargs)


def subscription(**kwargs):  # noqa: ANN003, ANN201
    """A subscription: what it streams is read, so an app needs ``dokuments_read`` for it."""
    return strawberry.subscription(extensions=[AuthSubscribeExtension(scopes=["dokuments_read"])], **kwargs)


@strawberry.type
class Query:
    files: list[types.File] = field()
    documents: list[types.Document] = field()
    pages: list[types.Page] = field()

    @field(permission_classes=[])
    def file(self, info: Info, id: ID) -> types.File:
        return models.File.objects.get(id=id, organization=info.context.request.organization)

    @field(permission_classes=[])
    def document(self, info: Info, id: ID) -> types.Document:
        return models.Document.objects.get(id=id, file__organization=info.context.request.organization)

    @field(permission_classes=[])
    def page(self, info: Info, id: ID) -> types.Page:
        return models.Page.objects.get(id=id, document__file__organization=info.context.request.organization)


def upload_mutation(**kwargs):  # noqa: ANN003, ANN201
    """A mutation that hands out or finishes upload credentials: an app needs ``dokuments_write`` for it,
    a member one of ``datalayer.upload_roles`` (``dokuments_editor`` when none are configured)."""
    roles = load_config().upload_roles or [EDITOR]
    return strawberry_django.mutation(extensions=[AuthExtension(scopes=["dokuments_write"], any_role_of=roles)], **kwargs)


@strawberry.type
class Mutation:
    # Uploads (arkitekt_datalayer): request a grant, write the file to S3, finish, then file it.
    request_media_upload = upload_mutation(resolver=datalayer_mutations.request_media_upload, description="Request temporary S3 credentials to upload one file (a document, or a page's image).")
    finish_media_upload = upload_mutation(resolver=datalayer_mutations.finish_media_upload, description="Finalize an upload after the client has written the object.")
    refresh_media_upload = upload_mutation(
        description="Reissue upload credentials for a media upload still in flight, to the same key, so a write that outlives its credentials carries on. Only the uploader may, never for a finished store, and never past the upload's time limit",
        resolver=datalayer_mutations.refresh_media_upload,
    )
    request_media_access = access_mutation(resolver=datalayer_mutations.request_media_access, description="Request temporary S3 read credentials for an uploaded file.")
    request_general_media_access = access_mutation(resolver=datalayer_mutations.request_general_media_access, description="Request temporary S3 read credentials for the organization's files.")

    # File
    from_file_like = mutation(resolver=mutations.from_file_like, description="Create a file from file-like data")
    delete_file = mutation(resolver=mutations.delete_file, description="Delete an existing file")

    # Experiment
    create_document = mutation(resolver=mutations.create_document, description="Create a new document")

    # Page
    create_page = mutation(resolver=mutations.create_page, description="Create a new page in a document")


@strawberry.type
class Subscription:
    """The root subscription type"""

    files = subscription(resolver=subscriptions.files, description="Subscribe to real-time file updates")


# A federation schema: the datalayer's store types are federated entities carrying ``@key``.
class Schema(QuietErrorsSchema, strawberry.federation.Schema):
    """strawberry.federation.Schema, logging expected resolver errors as one line and bugs with a traceback (see logs.py)."""


schema = Schema(
    query=Query,
    subscription=Subscription,
    mutation=Mutation,
    extensions=[
        KoherentExtension,
        AuthentikateExtension,
        DjangoOptimizerExtension,
    ],
    config=StrawberryConfig(scalar_map={**datalayer_scalars.SCALAR_MAP}),
    types=[],
)

# What stands for every scope and role here (`dokuments_all`, `dokuments_admin`). dokuments has no
# hub structures, so no `annotate_schema`: the contract's catch-alls are declared directly.
declare_catch_alls(scope=contract.description.all_scope, role=contract.description.admin_role)
