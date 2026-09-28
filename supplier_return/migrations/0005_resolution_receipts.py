from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('supplier_return', '0004_shipping_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='supplierreturnresolution',
            name='resolution_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='SupplierReturnReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=10, max_digits=25)),
                ('stock_item_id', models.PositiveIntegerField(blank=True, db_index=True, null=True)),
                ('location_id', models.PositiveIntegerField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('resolution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='receipts', to='supplier_return.supplierreturnresolution')),
            ],
            options={'ordering': ['received_at', 'pk']},
        ),
    ]
