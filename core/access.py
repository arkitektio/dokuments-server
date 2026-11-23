"""Reading a stored file's bytes: for a member, any finished store of the organization; for a guest,
only one in their collaborations (a shared file's bytes, or its pages' images)."""

from arkitekt_datalayer import inputs, models, types
from arkitekt_datalayer.datalayer import get_current_datalayer
from arkitekt_service.collaborations.guests import object_scope
from kante.types import Info


def request_media_access(
    info: Info, input: inputs.RequestMediaAccessInput
) -> types.MediaAccessGrant:
    """Temporary S3 read credentials for one finished media store of the organization.

    The store is looked up at the root field, so a guest of the organization finds only what is in
    one of their collaborations: another store of the organization is not found.
    """
    store_id = input.to_pydantic().store_id
    stores = object_scope(
        models.MediaStore.objects.filter(
            organization=info.context.request.organization,
            populated=True,
            orphaned_at__isnull=True,
        ),
        info=info,
    )
    store = stores.get(id=store_id)
    return types.MediaAccessGrant.from_pydantic(
        get_current_datalayer().generate_media_access_grant(store)
    )
