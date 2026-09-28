from django.conf import settings
from django.db import models
from django.utils import timezone


class SupplierReturn(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        READY = "READY", "Ready to Return"
        SHIPPED = "SHIPPED", "Shipped"
        AWAITING = "AWAITING", "Awaiting Resolution"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Resolution(models.TextChoices):
        REPLACEMENT = "REPLACEMENT", "Replacement"
        CREDIT = "CREDIT", "Credit"
        REFUND = "REFUND", "Refund"
        REWORK = "REWORK", "Repair / Rework"
        OTHER = "OTHER", "Other"

    purchase_order = models.ForeignKey("order.PurchaseOrder", on_delete=models.PROTECT, related_name="supplier_returns")
    supplier_rma = models.CharField(max_length=100, blank=True)
    redmine_issue = models.CharField(max_length=255, blank=True)
    requested_resolution = models.CharField(max_length=20, choices=Resolution.choices, default=Resolution.REPLACEMENT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)

    holding_location = models.ForeignKey("stock.StockLocation", on_delete=models.PROTECT, null=True, blank=True, related_name="supplier_returns_holding")
    external_location = models.ForeignKey("stock.StockLocation", on_delete=models.PROTECT, null=True, blank=True, related_name="supplier_returns_external")
    receiving_location = models.ForeignKey("stock.StockLocation", on_delete=models.PROTECT, null=True, blank=True, related_name="supplier_returns_receiving")

    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=255, blank=True)
    shipped_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="supplier_returns_created")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    closed_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    @property
    def reference(self):
        return f"SR-{self.pk:04d}" if self.pk else "SR-NEW"

    def close_if_resolved(self):
        lines = list(self.lines.all())
        if lines and all(line.outstanding_quantity <= 0 for line in lines):
            self.status = self.Status.CLOSED
            self.closed_date = timezone.localdate()
            self.save(update_fields=["status", "closed_date", "updated"])
            return True
        return False

    @classmethod
    def check_user_permission(cls, user, permission):
        return bool(user and user.is_authenticated)

    def __str__(self):
        return f"{self.reference} / {self.purchase_order}"


class SupplierReturnLine(models.Model):
    class Reason(models.TextChoices):
        DEFECTIVE = "DEFECTIVE", "Defective / Failed Inspection"
        INCORRECT = "INCORRECT", "Incorrect Material"
        DAMAGED = "DAMAGED", "Damaged"
        NOT_REQUIRED = "NOT_REQUIRED", "No Longer Required"
        ORDER_ERROR = "ORDER_ERROR", "Ordered in Error"
        OTHER = "OTHER", "Other"

    supplier_return = models.ForeignKey(SupplierReturn, on_delete=models.CASCADE, related_name="lines")
    po_line = models.ForeignKey("order.PurchaseOrderLineItem", on_delete=models.PROTECT, related_name="supplier_return_lines")
    stock_item = models.ForeignKey("stock.StockItem", on_delete=models.PROTECT, related_name="supplier_return_lines")
    quantity = models.DecimalField(max_digits=15, decimal_places=5)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    requested_resolution = models.CharField(max_length=20, choices=SupplierReturn.Resolution.choices)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["pk"]

    @property
    def resolved_quantity(self):
        return sum((r.quantity for r in self.resolutions.all()), start=0)

    @property
    def outstanding_quantity(self):
        return max(self.quantity - self.resolved_quantity, 0)

    @classmethod
    def check_user_permission(cls, user, permission):
        return bool(user and user.is_authenticated)


class SupplierReturnReceipt(models.Model):
    class ReceiptType(models.TextChoices):
        REWORKED = "REWORKED", "Reworked Original"
        REPLACEMENT = "REPLACEMENT", "Replacement"

    line = models.ForeignKey(SupplierReturnLine, on_delete=models.CASCADE, related_name="receipts")
    receipt_type = models.CharField(max_length=20, choices=ReceiptType.choices)
    quantity = models.DecimalField(max_digits=15, decimal_places=5)
    original_stock_item = models.ForeignKey("stock.StockItem", on_delete=models.PROTECT, related_name="supplier_return_receipts_as_original")
    received_stock_item = models.ForeignKey("stock.StockItem", on_delete=models.PROTECT, related_name="supplier_return_receipts_as_received")
    received_date = models.DateField(default=timezone.localdate)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)


class SupplierReturnResolution(models.Model):
    line = models.ForeignKey(SupplierReturnLine, on_delete=models.CASCADE, related_name="resolutions")
    resolution_type = models.CharField(max_length=20, choices=SupplierReturn.Resolution.choices)
    quantity = models.DecimalField(max_digits=15, decimal_places=5)
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    reference = models.CharField(max_length=255, blank=True)
    resolution_date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
