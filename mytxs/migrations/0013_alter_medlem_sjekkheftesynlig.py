# Generated by Django 4.2 on 2024-05-03 12:48

from django.db import migrations
import mytxs.fields


class Migration(migrations.Migration):

    dependencies = [
        ('mytxs', '0012_alter_hendelse_kategori'),
    ]

    operations = [
        migrations.AlterField(
            model_name='medlem',
            name='sjekkhefteSynlig',
            field=mytxs.fields.BitmapMultipleChoiceField(blank=True, choicesList=['fødselsdato', 'epost', 'tlf', 'studieEllerJobb', 'boAdresse', 'foreldreAdresse'], default=0, editable=False, verbose_name='Synlig i sjekkheftet'),
        ),
    ]
