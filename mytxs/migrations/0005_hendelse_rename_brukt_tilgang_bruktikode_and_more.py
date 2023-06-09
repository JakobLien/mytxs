# Generated by Django 4.2 on 2023-06-28 18:20

from django.db import migrations, models
import django.db.models.deletion
import mytxs.fields


class Migration(migrations.Migration):

    dependencies = [
        ('mytxs', '0004_alter_dekorasjoninnehavelse_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Hendelse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('navn', models.CharField(max_length=60)),
                ('beskrivelse', models.CharField(blank=True, max_length=150)),
                ('sted', models.CharField(blank=True, max_length=50)),
                ('kategori', models.CharField(choices=[('O', 'Oblig'), ('P', 'Påmelding'), ('F', 'Frivillig')], max_length=1)),
                ('startDate', mytxs.fields.MyDateField()),
                ('startTime', mytxs.fields.MyTimeField(blank=True, null=True)),
                ('sluttDate', mytxs.fields.MyDateField(blank=True, null=True)),
                ('sluttTime', mytxs.fields.MyTimeField(blank=True, null=True)),
                ('kor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='mytxs.kor')),
            ],
            options={
                'ordering': ['startDate', 'startTime'],
            },
        ),
        migrations.RenameField(
            model_name='tilgang',
            old_name='brukt',
            new_name='bruktIKode',
        ),
        migrations.AddField(
            model_name='verv',
            name='bruktIKode',
            field=models.BooleanField(default=False, help_text='<span title="Hvorvidt vervet er brukt i kode og følgelig ikke kan endres på av brukere.">(?)</span>'),
        ),
        migrations.AlterUniqueTogether(
            name='dekorasjoninnehavelse',
            unique_together={('medlem', 'dekorasjon', 'start')},
        ),
        migrations.AlterUniqueTogether(
            name='vervinnehavelse',
            unique_together={('medlem', 'verv', 'start')},
        ),
        migrations.CreateModel(
            name='Lenke',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('navn', models.CharField(max_length=255)),
                ('lenke', models.CharField(max_length=255)),
                ('kor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lenker', to='mytxs.kor')),
            ],
            options={
                'ordering': ['kor'],
            },
        ),
        migrations.CreateModel(
            name='Oppmøte',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fravær', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('ankomst', models.IntegerField(choices=[(1, 'Kommer'), (0, 'Kommer kanskje'), (-1, 'Kommer ikke')], default=0)),
                ('melding', models.TextField(blank=True)),
                ('gyldig', models.BooleanField(default=False)),
                ('hendelse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='oppmøter', to='mytxs.hendelse')),
                ('medlem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='oppmøter', to='mytxs.medlem')),
            ],
            options={
                'ordering': ['-ankomst'],
                'unique_together': {('medlem', 'hendelse')},
            },
        ),
    ]
