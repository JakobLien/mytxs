# Generated by Django 4.1.7 on 2023-04-26 13:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mytxs', '0010_alter_medlem_bilde_alter_medlem_etternavn_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='verv',
            options={'ordering': ['kor', models.Case(models.When(navn='1S', then=0), models.When(navn='2S', then=1), models.When(navn='1A', then=2), models.When(navn='2A', then=3), models.When(navn='1T', then=4), models.When(navn='2T', then=5), models.When(navn='1B', then=6), models.When(navn='2B', then=7), default=8), 'navn']},
        ),
    ]
