from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('supplier_return', '0005_resolution_receipts')]
    operations = [
        migrations.AddField(
            model_name='supplierreturnresolution',
            name='ready_to_receive',
            field=models.BooleanField(default=False),
        ),
    ]
