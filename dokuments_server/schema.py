from kante.types import Info
from dokuments_server.logs import QuietErrorsSchema
import strawberry

from arkitekt_datalayer import mutations as datalayer_mutations
from arkitekt_datalayer import scalars as datalayer_scalars
from arkitekt_datalayer.datalayer import load_config
from authentikate.strawberry.directives import AuthExtension
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


ID = Annotated[StrawberryID, strawberry.argument(description="The unique identifier of an object")]


@strawberry.type
class Query:
    files: list[types.File] = strawberry_django.field()
    documents: list[types.Document] = strawberry_django.field()
    pages: list[types.Page] = strawberry_django.field()

    @strawberry_django.field(permission_classes=[])
    def file(self, info: Info, id: ID) -> types.File:
        return models.File.objects.get(id=id, organization=info.context.request.organization)

    @strawberry_django.field(permission_classes=[])
    def document(self, info: Info, id: ID) -> types.Document:
        return models.Document.objects.get(id=id, file__organization=info.context.request.organization)

    @strawberry_django.field(permission_classes=[])
    def page(self, info: Info, id: ID) -> types.Page:
        return models.Page.objects.get(id=id, document__file__organization=info.context.request.organization)


def upload_mutation(**kwargs):  # noqa: ANN003, ANN201
    """A mutation that hands out or finishes upload credentials: gated by ``datalayer.upload_roles``."""
    return strawberry_django.mutation(extensions=[AuthExtension(any_role_of=load_config().upload_roles)], **kwargs)


@strawberry.type
class Mutation:
    # Uploads (arkitekt_datalayer): request a grant, write the file to S3, finish, then file it.
    request_media_upload = upload_mutation(resolver=datalayer_mutations.request_media_upload, description="Request temporary S3 credentials to upload one file (a document, or a page's image).")
    finish_media_upload = upload_mutation(resolver=datalayer_mutations.finish_media_upload, description="Finalize an upload after the client has written the object.")
    request_media_access = strawberry_django.mutation(resolver=datalayer_mutations.request_media_access, description="Request temporary S3 read credentials for an uploaded file.")
    request_general_media_access = strawberry_django.mutation(resolver=datalayer_mutations.request_general_media_access, description="Request temporary S3 read credentials for the organization's files.")

    # File
    from_file_like = strawberry_django.mutation(resolver=mutations.from_file_like, description="Create a file from file-like data")
    delete_file = strawberry_django.mutation(resolver=mutations.delete_file, description="Delete an existing file")

    # Experiment
    create_document = strawberry_django.mutation(resolver=mutations.create_document, description="Create a new document")

    # Page
    create_page = strawberry_django.mutation(resolver=mutations.create_page, description="Create a new page in a document")


@strawberry.type
class Subscription:
    """The root subscription type"""

    files = strawberry.subscription(resolver=subscriptions.files, description="Subscribe to real-time file updates")


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
