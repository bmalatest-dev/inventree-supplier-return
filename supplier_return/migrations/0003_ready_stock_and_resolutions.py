from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('supplier_return', '0002_update_reason_choices'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='supplierreturnline',
            name='original_location_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='supplierreturnline',
            name='return_stock_item_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='supplierreturn',
            name='status',
            field=models.CharField(choices=[('DRAFT', 'Draft'), ('READY', 'Ready to Return'), ('SHIPPED', 'Shipped / Awaiting Resolution'), ('CLOSED', 'Closed'), ('CANCELLED', 'Cancelled')], default='DRAFT', max_length=16),
        ),
        migrations.CreateModel(
            name='SupplierReturnResolution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resolution', models.CharField(choices=[('REPLACEMENT', 'Replacement'), ('CREDIT', 'Credit'), ('REFUND', 'Refund'), ('REWORK', 'Repair / Rework'), ('OTHER', 'Other')], max_length=32)),
                ('quantity', models.DecimalField(decimal_places=10, max_digits=25)),
                ('replacement_stock_item_id', models.PositiveIntegerField(blank=True, null=True)),
                ('reference', models.CharField(blank=True, max_length=255)),
                ('amount', models.DecimalField(blank=True, decimal_places=6, max_digits=25, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('line', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actual_resolutions', to='supplier_return.supplierreturnline')),
            ],
            options={'ordering': ['created_at', 'pk']},
        ),
    ]
