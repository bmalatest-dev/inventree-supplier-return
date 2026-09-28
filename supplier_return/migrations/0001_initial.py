from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("order", "0001_initial"),
        ("stock", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SupplierReturn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("supplier_rma", models.CharField(blank=True, max_length=100)),
                ("redmine_issue", models.CharField(blank=True, max_length=255)),
                ("requested_resolution", models.CharField(choices=[("REPLACEMENT", "Replacement"), ("CREDIT", "Credit"), ("REFUND", "Refund"), ("REWORK", "Repair / Rework"), ("OTHER", "Other")], default="REPLACEMENT", max_length=20)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("READY", "Ready to Return"), ("SHIPPED", "Shipped"), ("AWAITING", "Awaiting Resolution"), ("CLOSED", "Closed"), ("CANCELLED", "Cancelled")], default="DRAFT", max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("carrier", models.CharField(blank=True, max_length=100)),
                ("tracking_number", models.CharField(blank=True, max_length=255)),
                ("shipped_date", models.DateField(blank=True, null=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("closed_date", models.DateField(blank=True, null=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="supplier_returns_created", to=settings.AUTH_USER_MODEL)),
                ("external_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplier_returns_external", to="stock.stocklocation")),
                ("holding_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplier_returns_holding", to="stock.stocklocation")),
                ("purchase_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_returns", to="order.purchaseorder")),
                ("receiving_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplier_returns_receiving", to="stock.stocklocation")),
            ],
            options={"ordering": ["-created"]},
        ),
        migrations.CreateModel(
            name="SupplierReturnLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.DecimalField(decimal_places=5, max_digits=15)),
                ("reason", models.CharField(choices=[("DEFECTIVE", "Defective / Failed Inspection"), ("INCORRECT", "Incorrect Material"), ("DAMAGED", "Damaged"), ("NOT_REQUIRED", "No Longer Required"), ("ORDER_ERROR", "Ordered in Error"), ("OTHER", "Other")], max_length=20)),
                ("requested_resolution", models.CharField(choices=[("REPLACEMENT", "Replacement"), ("CREDIT", "Credit"), ("REFUND", "Refund"), ("REWORK", "Repair / Rework"), ("OTHER", "Other")], max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("po_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_return_lines", to="order.purchaseorderlineitem")),
                ("stock_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_return_lines", to="stock.stockitem")),
                ("supplier_return", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="supplier_return.supplierreturn")),
            ],
            options={"ordering": ["pk"]},
        ),
        migrations.CreateModel(
            name="SupplierReturnReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("receipt_type", models.CharField(choices=[("REWORKED", "Reworked Original"), ("REPLACEMENT", "Replacement")], max_length=20)),
                ("quantity", models.DecimalField(decimal_places=5, max_digits=15)),
                ("received_date", models.DateField(default=django.utils.timezone.localdate)),
                ("notes", models.TextField(blank=True)),
                ("line", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="receipts", to="supplier_return.supplierreturnline")),
                ("original_stock_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_return_receipts_as_original", to="stock.stockitem")),
                ("received_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("received_stock_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_return_receipts_as_received", to="stock.stockitem")),
            ],
        ),
        migrations.CreateModel(
            name="SupplierReturnResolution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("resolution_type", models.CharField(choices=[("REPLACEMENT", "Replacement"), ("CREDIT", "Credit"), ("REFUND", "Refund"), ("REWORK", "Repair / Rework"), ("OTHER", "Other")], max_length=20)),
                ("quantity", models.DecimalField(decimal_places=5, max_digits=15)),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ("reference", models.CharField(blank=True, max_length=255)),
                ("resolution_date", models.DateField(default=django.utils.timezone.localdate)),
                ("notes", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("line", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resolutions", to="supplier_return.supplierreturnline")),
            ],
        ),
    ]
