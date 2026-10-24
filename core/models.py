from django.db import models
from django.contrib.auth import get_user_model
from taggit.managers import TaggableManager
from koherent.fields import ProvenanceField
from authentikate.models import Organization

# Create your models here.


class DatasetManager(models.Manager):
    def get_current_default_for_user_and_organization(self, user, organization):
        potential = self.filter(creator=user, organization=organization, is_default=True).first()
        if not potential:
            return self.create(creator=user, organization=organization, name="Default", is_default=True)

        return potential


class Dataset(models.Model):
    """
    A dataset is a collection of data files and metadata files.
    It mimics the concept of a folder in a file system and is the top level
    object in the data model.

    """

    creator = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="created_datasets",
        help_text="The user that created the dataset",
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="The time the dataset was created")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    name = models.CharField(max_length=200, help_text="The name of the dataset")
    description_two = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        help_text="The description of the dataset, this is a second description field",
    )
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    description = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        help_text="The description of the dataset",
    )
    pinned_by = models.ManyToManyField(
        get_user_model(),
        related_name="pinned_datasets",
        blank=True,
        help_text="The users that have pinned the dataset",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether the dataset is the current default dataset for the user",
    )
    provenance = ProvenanceField()
    tags = TaggableManager()

    objects = DatasetManager()

    def __str__(self) -> str:
        return super().__str__()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["creator", "is_default", "organization"],
                name="unique_default_per_creator",
                condition=models.Q(is_default=True),
            ),
            models.UniqueConstraint(
                fields=["parent", "name"],
                name="only_one_dataset_per_parent_and_name",
            ),
        ]


class File(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, null=True, blank=True, related_name="files")
    store = models.ForeignKey(
        "datalayer.MediaStore",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="files",
        help_text="The stored file: a media store of the file's organization, uploaded with requestMediaUpload and finished with finishMediaUpload.",
    )
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
    tags = TaggableManager()
    name = models.CharField(max_length=1000, help_text="The name of the file", default="")
    created_at = models.DateTimeField(auto_now_add=True)
    creator = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, null=True)


class Document(models.Model):
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)


class Page(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="pages")
    index = models.PositiveIntegerField()
    content = models.TextField(null=True, blank=True)
    image = models.ForeignKey("datalayer.MediaStore", on_delete=models.CASCADE, related_name="pages", help_text="The page's image: a media store of the document's organization.")
    ocr_result = models.JSONField(null=True, blank=True)

    def get_text(self):
        """Concatenate recognized lines into full-page text"""
        if not self.ocr_result:
            return ""
        return "\n".join([line["text"] for line in self.ocr_result.get("textlines", [])])


