# Generated by Django 4.2.11 on 2024-04-24 18:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("prices", "0008_alter_forecastdata_forecast"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="history",
            name="demand_source",
        ),
    ]
