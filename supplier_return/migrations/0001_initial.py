from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='SupplierReturn', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('reference', models.CharField(blank=True, max_length=32, unique=True)),
            ('purchase_order_id', models.PositiveIntegerField(db_index=True)),
            ('supplier_rma', models.CharField(blank=True, max_length=128)),
            ('status', models.CharField(choices=[('DRAFT','Draft'),('READY','Ready to Return'),('CANCELLED','Cancelled')], default='DRAFT', max_length=16)),
            ('holding_location_id', models.PositiveIntegerField(blank=True, null=True)),
            ('redmine_issue', models.CharField(blank=True, max_length=255)),
            ('notes', models.TextField(blank=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ], options={'ordering':['-created_at','-pk']}),
        migrations.CreateModel(name='SupplierReturnLine', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('purchase_order_line_id', models.PositiveIntegerField(blank=True, null=True)),
            ('stock_item_id', models.PositiveIntegerField(db_index=True)),
            ('quantity', models.DecimalField(decimal_places=10, max_digits=25)),
            ('reason', models.CharField(choices=[('DEFECTIVE','Defective / Failed Inspection'),('INCORRECT','Incorrect Material'),('DAMAGED','Damaged'),('NOT_REQUIRED','No Longer Required'),('ORDERED_ERROR','Ordered in Error'),('OTHER','Other')], max_length=32)),
            ('requested_resolution', models.CharField(choices=[('REPLACEMENT','Replacement'),('CREDIT','Credit'),('REFUND','Refund'),('REWORK','Repair / Rework'),('OTHER','Other')], max_length=32)),
            ('notes', models.TextField(blank=True)),
            ('supplier_return', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='supplier_return.supplierreturn')),
        ], options={'ordering':['pk']}),
        migrations.CreateModel(name='SupplierReturnEvent', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('event_type', models.CharField(max_length=64)),
            ('timestamp', models.DateTimeField(auto_now_add=True)),
            ('notes', models.TextField(blank=True)),
            ('supplier_return', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='supplier_return.supplierreturn')),
            ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ], options={'ordering':['timestamp','pk']}),
    ]
