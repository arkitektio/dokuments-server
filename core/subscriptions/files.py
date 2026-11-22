import logging
from collections.abc import AsyncGenerator

import strawberry
from kante.types import Info

from core import channels, models, types

logger = logging.getLogger(__name__)


@strawberry.type
class FileEvent:
    create: types.File | None = None
    delete: strawberry.ID | None = None
    update: types.File | None = None
    moved: types.File | None = None


async def files(
    self: object,
    info: Info,
    dataset: strawberry.ID | None = None,
) -> AsyncGenerator[FileEvent, None]:
    """File events of the caller's organization, of one dataset's files when ``dataset`` is given.

    Listens on the organization's group, so another organization's files never arrive. A
    deletion names only an id, so it is passed on whichever dataset the file was in.
    """
    organization = info.context.request.organization
    in_scope = models.File.objects.filter(organization=organization)
    if dataset is not None:
        in_scope = in_scope.filter(dataset_id=dataset)

    async for message in channels.file_channel.listen(
        info.context, [channels.org_files_group(organization.id)]
    ):
        logger.debug("File channel message: %s", message)
        if message.delete:
            yield FileEvent(delete=strawberry.ID(str(message.delete)))
            continue
        file_id = message.create or message.update
        file = await in_scope.filter(id=file_id).afirst()
        if file is None:
            continue
        yield FileEvent(create=file) if message.create else FileEvent(update=file)
