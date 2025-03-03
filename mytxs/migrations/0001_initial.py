# Generated by Django 4.2 on 2023-05-01 20:14

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import mytxs.fields
import mytxs.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Dekorasjon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('navn', models.CharField(max_length=30)),
            ],
            options={
                'ordering': ['kor', 'navn'],
            },
        ),
        migrations.CreateModel(
            name='Kor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kortTittel', models.CharField(max_length=3)),
                ('langTittel', models.CharField(max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='Medlem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fornavn', models.CharField(default='Autogenerert', max_length=50)),
                ('mellomnavn', models.CharField(blank=True, default='', max_length=50)),
                ('etternavn', models.CharField(default='Testbruker', max_length=50)),
                ('fødselsdato', mytxs.fields.MyDateField(blank=True, null=True)),
                ('epost', models.EmailField(blank=True, max_length=100)),
                ('tlf', models.BigIntegerField(blank=True, null=True)),
                ('studieEllerJobb', models.CharField(blank=True, max_length=100)),
                ('boAdresse', models.CharField(blank=True, max_length=100)),
                ('foreldreAdresse', models.CharField(blank=True, max_length=100)),
                ('bilde', models.ImageField(blank=True, null=True, upload_to=mytxs.models.Medlem.bildeUploadTo)),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='medlem', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Tilgang',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('navn', models.CharField(max_length=50, unique=True)),
            ],
            options={
                'ordering': ['navn'],
            },
        ),
        migrations.CreateModel(
            name='Verv',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('navn', models.CharField(max_length=30)),
                ('kor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='verv', to='mytxs.kor')),
                ('tilganger', models.ManyToManyField(blank=True, related_name='verv', to='mytxs.tilgang')),
            ],
            options={
                'ordering': ['kor', models.Case(models.When(navn='1S', then=0), models.When(navn='2S', then=1), models.When(navn='1A', then=2), models.When(navn='2A', then=3), models.When(navn='1T', then=4), models.When(navn='2T', then=5), models.When(navn='1B', then=6), models.When(navn='2B', then=7), default=8), 'navn'],
                'unique_together': {('navn', 'kor')},
            },
        ),
        migrations.CreateModel(
            name='VervInnehavelse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start', mytxs.fields.MyDateField()),
                ('slutt', mytxs.fields.MyDateField(blank=True, null=True)),
                ('medlem', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vervInnehavelse', to='mytxs.medlem')),
                ('verv', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='vervInnehavelse', to='mytxs.verv')),
            ],
            options={
                'ordering': ['start'],
            },
        ),
        migrations.CreateModel(
            name='DekorasjonInnehavelse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start', mytxs.fields.MyDateField()),
                ('dekorasjon', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='dekorasjonInnehavelse', to='mytxs.dekorasjon')),
                ('medlem', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='dekorasjonInnehavelse', to='mytxs.medlem')),
            ],
            options={
                'ordering': ['start'],
            },
        ),
        migrations.AddField(
            model_name='dekorasjon',
            name='kor',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='dekorasjoner', to='mytxs.kor'),
        ),
        migrations.AlterUniqueTogether(
            name='dekorasjon',
            unique_together={('navn', 'kor')},
        ),
    ]
