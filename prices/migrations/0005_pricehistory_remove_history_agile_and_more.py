# Generated by Django 4.2.11 on 2024-04-24 12:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("prices", "0004_rename_irradience_forecastdata_rad_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PriceHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("day_ahead", models.FloatField()),
                ("agile", models.FloatField()),
            ],
        ),
        migrations.RemoveField(
            model_name="history",
            name="agile",
        ),
        migrations.RemoveField(
            model_name="history",
            name="day_ahead",
        ),
    ]
