import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """koherent 4: a historical row names the task it was made in (``task``), not an assignation.

    The old ``assignation_id`` column leaves the model's state only: it stays in the table, nullable,
    so the previous release still writes its history rows after a rollback.
    """

    dependencies = [
        ("core", "0001_initial"),
        ("koherent", "0004_index_root_task_id"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="historicaldataset",
                    name="assignation_id",
                ),
            ],
            database_operations=[],
        ),
        migrations.AddField(
            model_name="historicaldataset",
            name="task",
            field=models.ForeignKey(
                blank=True,
                help_text="The task during which the change occurred, if any",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="koherent.task",
            ),
        ),
    ]
