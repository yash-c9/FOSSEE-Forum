# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2017-05-23 06:21
from __future__ import unicode_literals

from django.db import migrations
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0002_auto_20150616_2121'),
        ('website', '0002_question_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='fosscategory',
            name='tag',
            field=taggit.managers.TaggableManager(help_text='A comma-separated list of tags.', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags'),
        ),
    ]