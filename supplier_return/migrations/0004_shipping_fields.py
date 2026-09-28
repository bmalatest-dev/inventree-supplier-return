from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('supplier_return', '0003_ready_stock_and_resolutions'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplierreturn',
            name='external_location_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='supplierreturn',
            name='shipment_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='supplierreturn',
            name='carrier',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='supplierreturn',
            name='tracking_number',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='supplierreturn',
            name='shipment_notes',
            field=models.TextField(blank=True),
        ),
    ]
