# Generated by Django 4.2 on 2024-02-29 09:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mytxs', '0011_alter_hendelse_beskrivelse'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hendelse',
            name='kategori',
            field=models.CharField(choices=[('O', 'Oblig'), ('P', 'Påmelding'), ('F', 'Frivillig'), ('U', 'Undergruppe')], default='O', help_text='<span title="Ikke endre dette uten grunn!">(?)</span>', max_length=1),
        ),
    ]