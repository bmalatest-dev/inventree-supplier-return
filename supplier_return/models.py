from django.conf import settings
from django.db import models


class SupplierReturn(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        READY = 'READY', 'Ready to Return'
        CANCELLED = 'CANCELLED', 'Cancelled'

    reference = models.CharField(max_length=32, unique=True, blank=True)
    purchase_order_id = models.PositiveIntegerField(db_index=True)
    supplier_rma = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    holding_location_id = models.PositiveIntegerField(null=True, blank=True)
    redmine_issue = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def save(self, *args, **kwargs):
        new = self.pk is None
        super().save(*args, **kwargs)
        if new and not self.reference:
            self.reference = f'SR-{self.pk:04d}'
            super().save(update_fields=['reference'])

    @classmethod
    def check_user_permission(cls, user, permission):
        return bool(user and user.is_authenticated)


class SupplierReturnLine(models.Model):
    class Reason(models.TextChoices):
        DEFECTIVE = 'DEFECTIVE', 'Defective / Failed Inspection'
        INCORRECT = 'INCORRECT', 'Incorrect Material'
        DAMAGED = 'DAMAGED', 'Damaged'
        NOT_REQUIRED = 'NOT_REQUIRED', 'No Longer Required'
        ORDERED_ERROR = 'ORDERED_ERROR', 'Ordered in Error'
        OTHER = 'OTHER', 'Other'

    class Resolution(models.TextChoices):
        REPLACEMENT = 'REPLACEMENT', 'Replacement'
        CREDIT = 'CREDIT', 'Credit'
        REFUND = 'REFUND', 'Refund'
        REWORK = 'REWORK', 'Repair / Rework'
        OTHER = 'OTHER', 'Other'

    supplier_return = models.ForeignKey(SupplierReturn, related_name='lines', on_delete=models.CASCADE)
    purchase_order_line_id = models.PositiveIntegerField(null=True, blank=True)
    stock_item_id = models.PositiveIntegerField(db_index=True)
    quantity = models.DecimalField(max_digits=25, decimal_places=10)
    reason = models.CharField(max_length=32, choices=Reason.choices)
    requested_resolution = models.CharField(max_length=32, choices=Resolution.choices)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['pk']

    @classmethod
    def check_user_permission(cls, user, permission):
        return bool(user and user.is_authenticated)


class SupplierReturnEvent(models.Model):
    supplier_return = models.ForeignKey(SupplierReturn, related_name='events', on_delete=models.CASCADE)
    event_type = models.CharField(max_length=64)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['timestamp', 'pk']

    @classmethod
    def check_user_permission(cls, user, permission):
        return bool(user and user.is_authenticated)
