from django.db import transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from core import models, channels


def _broadcast_file(signal: channels.FileSignal, file: models.File) -> None:
    """Publish a file signal to its organization's group, once the transaction commits.

    A per-organization group keeps another organization's files off every subscriber's
    stream: tenancy is a property of the group, not of a filter applied per message.
    """
    group = channels.org_files_group(file.organization_id)
    transaction.on_commit(lambda: channels.file_channel.broadcast(signal, [group]))


@receiver(post_save, sender=models.File)
def my_file_handler(sender, instance=None, created=None, **kwargs):
    if created:
        _broadcast_file(channels.FileSignal(create=instance.id), instance)
    else:
        _broadcast_file(channels.FileSignal(update=instance.id), instance)


@receiver(pre_delete, sender=models.File)
def my_file_delete_handler(sender, instance=None, **kwargs):
    _broadcast_file(channels.FileSignal(delete=instance.id), instance)
