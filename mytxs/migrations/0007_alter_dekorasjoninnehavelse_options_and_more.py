# Generated by Django 4.2 on 2023-10-05 21:02

from django.db import migrations, models
import django.db.models.deletion
import mytxs.fields


class Migration(migrations.Migration):

    dependencies = [
        ('mytxs', '0006_alter_oppmøte_options_alter_verv_options_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='dekorasjoninnehavelse',
            options={'ordering': ['-start', '-pk'], 'verbose_name_plural': 'dekorasjoninnehavelser'},
        ),
        migrations.AlterModelOptions(
            name='hendelse',
            options={'ordering': ['startDate', 'startTime', 'navn', 'kor'], 'verbose_name_plural': 'hendelser'},
        ),
        migrations.AlterModelOptions(
            name='lenke',
            options={'ordering': ['kor', 'navn', '-pk'], 'verbose_name_plural': 'lenker'},
        ),
        migrations.AlterModelOptions(
            name='logg',
            options={'ordering': ['-timeStamp', '-pk'], 'verbose_name_plural': 'logger'},
        ),
        migrations.AlterModelOptions(
            name='loggm2m',
            options={'ordering': ['-timeStamp', '-pk']},
        ),
        migrations.AlterModelOptions(
            name='medlem',
            options={'ordering': ['fornavn', 'mellomnavn', 'etternavn', '-pk'], 'verbose_name_plural': 'medlemmer'},
        ),
        migrations.AlterModelOptions(
            name='oppmøte',
            options={'ordering': ['-hendelse', 'medlem'], 'verbose_name_plural': 'oppmøter'},
        ),
        migrations.AlterModelOptions(
            name='vervinnehavelse',
            options={'ordering': ['-start', '-slutt', '-pk'], 'verbose_name_plural': 'vervinnehavelser'},
        ),
        migrations.RemoveField(
            model_name='kor',
            name='strRep',
        ),
        migrations.AddField(
            model_name='kor',
            name='stemmefordeling',
            field=models.CharField(blank=True, choices=[('SA', 'SA'), ('TB', 'TB'), ('SATB', 'SATB'), ('', '')], default=''),
        ),
        migrations.AddField(
            model_name='lenke',
            name='redirect',
            field=models.BooleanField(default=False, help_text='<span title="Om denne lenken skal kunne redirectes til">(?)</span>'),
        ),
        migrations.AddField(
            model_name='lenke',
            name='synlig',
            field=models.BooleanField(default=False, help_text='<span title="Om denne lenken skal være synlig på MyTXS">(?)</span>'),
        ),
        migrations.AddField(
            model_name='loggm2m',
            name='author',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='M2Mlogger', to='mytxs.medlem'),
        ),
        migrations.AddField(
            model_name='medlem',
            name='innstillinger',
            field=models.JSONField(default=dict, editable=False),
        ),
        migrations.AddField(
            model_name='medlem',
            name='sjekkhefteSynlig',
            field=mytxs.fields.BitmapMultipleChoiceField(blank=True, choicesList=['fødselsdato', 'epost', 'tlf', 'studieEllerJobb', 'boAdresse', 'foreldreAdresse'], default=0),
        ),
        migrations.AddField(
            model_name='turne',
            name='beskrivelse',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='hendelse',
            name='kategori',
            field=models.CharField(choices=[('O', 'Oblig'), ('P', 'Påmelding'), ('F', 'Frivillig')], default='O', help_text='<span title="Ikke endre dette uten grunn!">(?)</span>', max_length=1),
        ),
        migrations.AlterField(
            model_name='hendelse',
            name='kor',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='hendelser', to='mytxs.kor'),
        ),
        migrations.AlterField(
            model_name='hendelse',
            name='startDate',
            field=mytxs.fields.MyDateField(help_text='<span title="Oppmøtene for hendelsen, altså for fraværsføring og fraværsmelding, genereres av hvilke medlemmer som er aktive i koret på denne datoen, og ikke har permisjon">(?)</span>'),
        ),
        migrations.AlterField(
            model_name='oppmøte',
            name='ankomst',
            field=models.BooleanField(blank=True, choices=[(True, 'Kommer'), (None, 'Kommer kanskje'), (False, 'Kommer ikke')], default=None, null=True),
        ),
        migrations.AlterField(
            model_name='oppmøte',
            name='gyldig',
            field=models.BooleanField(blank=True, choices=[(True, 'Gyldig'), (None, 'Ikke behandlet'), (False, 'Ugyldig')], default=None, null=True),
        ),
        migrations.AlterField(
            model_name='vervinnehavelse',
            name='medlem',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vervInnehavelser', to='mytxs.medlem'),
        ),
        migrations.AlterField(
            model_name='vervinnehavelse',
            name='verv',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vervInnehavelser', to='mytxs.verv'),
        ),
        migrations.AlterUniqueTogether(
            name='hendelse',
            unique_together={('kor', 'navn', 'startDate')},
        ),
        migrations.AlterUniqueTogether(
            name='lenke',
            unique_together={('kor', 'navn', 'lenke')},
        ),
    ]
