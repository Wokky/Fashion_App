# Generated by Django 3.2.18 on 2023-03-26 23:32

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0023_auto_20230323_2348'),
    ]

    operations = [
        migrations.AddField(
            model_name='recommendedimage',
            name='related_product',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='related_product', to='store.producttest'),
        ),
    ]