"""Files: an uploaded media store of the organization, filed in a dataset."""

import strawberry
from arkitekt_datalayer.models import MediaStore
from kante.types import Info

from core import models, scalars, types


@strawberry.input
class PinFileInput:
    id: strawberry.ID
    pin: bool


def pin_file(
    info: Info,
    input: PinFileInput,
) -> types.File:
    raise NotImplementedError("TODO")


def organization_store(info: Info, store_id: str) -> MediaStore:
    """The caller's organization's finished media store; another organization's is not found."""
    try:
        store = MediaStore.objects.get(id=store_id, organization=info.context.request.organization)
    except MediaStore.DoesNotExist:
        raise PermissionError(f"No media store {store_id} in your organization.") from None
    if not store.populated:
        raise ValueError(f"Media store {store_id} has not been finished, so the file may still be arriving. Call `finishMediaUpload` once it is written.")
    return store


@strawberry.input
class FromFileLike:
    file: scalars.FileLike
    dataset: strawberry.ID | None = None
    origins: list[strawberry.ID] | None = None


def from_file_like(
    info: Info,
    input: FromFileLike,
) -> types.File:
    store = organization_store(info, str(input.file))

    dataset = (
        models.Dataset.objects.get(id=input.dataset, organization=info.context.request.organization)
        if input.dataset
        else models.Dataset.objects.get_current_default_for_user_and_organization(info.context.request.user, info.context.request.organization)
    )

    return models.File.objects.create(
        dataset=dataset,
        creator=info.context.request.user,
        organization=info.context.request.organization,
        name=store.original_file_name or store.key,
        store=store,
    )


@strawberry.input
class DeleteFileInput:
    id: strawberry.ID


def delete_file(
    info: Info,
    input: DeleteFileInput,
) -> strawberry.ID:
    models.File.objects.get(id=input.id, organization=info.context.request.organization).delete()
    return input.id
