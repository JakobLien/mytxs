# Generated by Django 4.2 on 2024-10-10 19:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mytxs', '0014_medlem_innlogginger'),
    ]

    operations = [
        migrations.AlterField(
            model_name='medlem',
            name='innlogginger',
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
    ]