# Generated by Django 2.2.13 on 2020-12-07 10:06

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0008_partnerschool'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('courses', '0034_program_topics'),
        ('dashboard', '0009_enrollment_hash_unique'),
    ]

    operations = [
        migrations.CreateModel(
            name='MicromastersLearnerRecordShare',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('partner_school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mail.PartnerSchool')),
                ('program', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.Program')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'program', 'partner_school')},
            },
        ),
    ]
