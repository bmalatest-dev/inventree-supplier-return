from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as http_status

from order.models import PurchaseOrder, PurchaseOrderLineItem
from stock.models import StockItem, StockLocation

from .models import SupplierReturn, SupplierReturnLine, SupplierReturnReceipt, SupplierReturnResolution


def _decimal(value, field="quantity"):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid {field}")
    if result <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return result


def _return_dict(obj, detail=False):
    po = obj.purchase_order
    data = {
        "pk": obj.pk,
        "reference": obj.reference,
        "purchase_order": po.pk,
        "purchase_order_reference": po.reference,
        "supplier": po.supplier_id,
        "supplier_name": po.supplier.name if po.supplier else "",
        "supplier_rma": obj.supplier_rma,
        "redmine_issue": obj.redmine_issue,
        "requested_resolution": obj.requested_resolution,
        "status": obj.status,
        "notes": obj.notes,
        "holding_location": obj.holding_location_id,
        "external_location": obj.external_location_id,
        "receiving_location": obj.receiving_location_id,
        "carrier": obj.carrier,
        "tracking_number": obj.tracking_number,
        "shipped_date": obj.shipped_date,
        "created": obj.created,
    }
    if detail:
        data["lines"] = [_line_dict(line) for line in obj.lines.select_related("po_line", "stock_item", "stock_item__part")]
    return data


def _line_dict(line):
    return {
        "pk": line.pk,
        "po_line": line.po_line_id,
        "stock_item": line.stock_item_id,
        "part": line.stock_item.part_id,
        "part_name": line.stock_item.part.full_name,
        "serial": line.stock_item.serial,
        "batch": line.stock_item.batch,
        "quantity": str(line.quantity),
        "reason": line.reason,
        "requested_resolution": line.requested_resolution,
        "resolved_quantity": str(line.resolved_quantity),
        "outstanding_quantity": str(line.outstanding_quantity),
        "notes": line.notes,
    }


def _find_po_line(po, item, supplied=None):
    if supplied:
        line = get_object_or_404(PurchaseOrderLineItem, pk=supplied)
        if line.order_id != po.pk:
            raise ValueError("Selected PO line does not belong to this Purchase Order")
        return line

    qs = po.lines.all()
    if item.supplier_part_id:
        qs = qs.filter(part_id=item.supplier_part_id)
    else:
        qs = qs.none()
    if qs.count() != 1:
        raise ValueError("PO line could not be determined uniquely; select the PO line explicitly")
    return qs.first()


def _move_stock(item, quantity, location, user, note):
    """Use InvenTree's native stock move operation and return the moved StockItem."""
    if location.structural:
        raise ValueError("Structural locations cannot hold stock")
    if quantity > item.quantity:
        raise ValueError("Return quantity exceeds stock quantity")
    if item.serialized and quantity != item.quantity:
        raise ValueError("Serialized stock must be returned as the complete Stock Item")

    original_pk = item.pk
    original_qty = item.quantity
    ok = item.move(location, note, user, quantity=quantity, purchaseorder=item.purchase_order)
    if not ok:
        raise ValueError("InvenTree could not move the selected stock")

    if quantity >= original_qty:
        return StockItem.objects.get(pk=original_pk)

    # Native partial move splits a child StockItem. Resolve the newly moved child.
    moved = (
        StockItem.objects.filter(parent_id=original_pk, location=location, quantity=quantity)
        .order_by("-pk")
        .first()
    )
    if not moved:
        raise ValueError("Stock was split but the moved Stock Item could not be identified")
    return moved


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def returns(request):
    if request.method == "GET":
        qs = SupplierReturn.objects.select_related("purchase_order", "purchase_order__supplier")
        po = request.query_params.get("purchase_order")
        stock_item = request.query_params.get("stock_item")
        if po:
            qs = qs.filter(purchase_order_id=po)
        if stock_item:
            qs = qs.filter(lines__stock_item_id=stock_item).distinct()
        return Response([_return_dict(x) for x in qs[:100]])

    data = request.data
    po = get_object_or_404(PurchaseOrder, pk=data.get("purchase_order"))
    holding = get_object_or_404(StockLocation, pk=data.get("holding_location"))

    with transaction.atomic():
        obj = SupplierReturn.objects.create(
            purchase_order=po,
            supplier_rma=data.get("supplier_rma", ""),
            redmine_issue=data.get("redmine_issue", ""),
            requested_resolution=data.get("requested_resolution", SupplierReturn.Resolution.REPLACEMENT),
            notes=data.get("notes", ""),
            holding_location=holding,
            created_by=request.user,
        )

        # Optional first line allows Create Supplier Return to be one operation from Stock Item.
        if data.get("stock_item"):
            _add_line(obj, data, request.user)

    return Response(_return_dict(obj, detail=True), status=http_status.HTTP_201_CREATED)


def _add_line(obj, data, user):
    if obj.status != SupplierReturn.Status.DRAFT:
        raise ValueError("Lines can only be added while the Supplier Return is in Draft")

    item = get_object_or_404(StockItem, pk=data.get("stock_item"))
    if item.purchase_order_id != obj.purchase_order_id:
        raise ValueError("Stock Item did not originate from this Purchase Order")

    qty = _decimal(data.get("quantity"))
    po_line = _find_po_line(obj.purchase_order, item, data.get("po_line"))
    resolution = data.get("requested_resolution", obj.requested_resolution)
    reason = data.get("reason", SupplierReturnLine.Reason.OTHER)

    moved_item = _move_stock(
        item,
        qty,
        obj.holding_location,
        user,
        f"{obj.reference}: moved to supplier return holding",
    )

    return SupplierReturnLine.objects.create(
        supplier_return=obj,
        po_line=po_line,
        stock_item=moved_item,
        quantity=qty,
        reason=reason,
        requested_resolution=resolution,
        notes=data.get("line_notes", ""),
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def return_detail(request, pk):
    obj = get_object_or_404(SupplierReturn.objects.select_related("purchase_order", "purchase_order__supplier"), pk=pk)
    return Response(_return_dict(obj, detail=True))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_line(request, pk):
    obj = get_object_or_404(SupplierReturn, pk=pk)
    try:
        with transaction.atomic():
            line = _add_line(obj, request.data, request.user)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response(_line_dict(line), status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ready(request, pk):
    obj = get_object_or_404(SupplierReturn, pk=pk)
    if not obj.lines.exists():
        return Response({"detail": "Add at least one return line first"}, status=400)
    if obj.status != SupplierReturn.Status.DRAFT:
        return Response({"detail": "Only Draft returns can be marked Ready"}, status=400)
    obj.status = SupplierReturn.Status.READY
    obj.save(update_fields=["status", "updated"])
    return Response(_return_dict(obj, detail=True))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ship(request, pk):
    obj = get_object_or_404(SupplierReturn, pk=pk)
    if obj.status not in {SupplierReturn.Status.DRAFT, SupplierReturn.Status.READY}:
        return Response({"detail": "Return is not ready to ship"}, status=400)

    external = get_object_or_404(StockLocation, pk=request.data.get("external_location"))
    try:
        with transaction.atomic():
            for line in obj.lines.select_related("stock_item"):
                item = StockItem.objects.get(pk=line.stock_item_id)
                _move_stock(item, line.quantity, external, request.user, f"{obj.reference}: shipped to supplier")

            obj.external_location = external
            obj.carrier = request.data.get("carrier", "")
            obj.tracking_number = request.data.get("tracking_number", "")
            obj.shipped_date = request.data.get("shipped_date") or timezone.localdate()
            obj.status = SupplierReturn.Status.AWAITING
            obj.save()
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)

    return Response(_return_dict(obj, detail=True))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def receive(request, pk, line_pk):
    obj = get_object_or_404(SupplierReturn, pk=pk)
    line = get_object_or_404(SupplierReturnLine, pk=line_pk, supplier_return=obj)
    location = get_object_or_404(StockLocation, pk=request.data.get("receiving_location"))
    receipt_type = request.data.get("receipt_type")
    qty = _decimal(request.data.get("quantity"))

    if qty > line.outstanding_quantity:
        return Response({"detail": "Received quantity exceeds unresolved return quantity"}, status=400)

    original = line.stock_item

    try:
        with transaction.atomic():
            if receipt_type == SupplierReturnReceipt.ReceiptType.REWORKED:
                # Preserve identity. For serialized items this is the exact same StockItem.
                received = _move_stock(original, qty, location, request.user, f"{obj.reference}: reworked stock received back; inspection required")
            elif receipt_type == SupplierReturnReceipt.ReceiptType.REPLACEMENT:
                serial = request.data.get("serial") or None
                batch = request.data.get("batch") or original.batch
                if original.serialized and not serial:
                    raise ValueError("A serial number is required for replacement of serialized stock")
                received = StockItem(
                    part=original.part,
                    supplier_part=original.supplier_part,
                    location=location,
                    quantity=qty,
                    serial=serial,
                    batch=batch,
                    status=original.status,  # preserve failed/inspection state until re-inspected
                    purchase_order=obj.purchase_order,
                    purchase_price=original.purchase_price,
                    packaging=original.packaging,
                )
                received.save(user=request.user, notes=f"{obj.reference}: replacement stock received; inspection required")
            else:
                raise ValueError("receipt_type must be REWORKED or REPLACEMENT")

            SupplierReturnReceipt.objects.create(
                line=line,
                receipt_type=receipt_type,
                quantity=qty,
                original_stock_item=original,
                received_stock_item=received,
                received_by=request.user,
                notes=request.data.get("notes", ""),
            )
            SupplierReturnResolution.objects.create(
                line=line,
                resolution_type=SupplierReturn.Resolution.REWORK if receipt_type == "REWORKED" else SupplierReturn.Resolution.REPLACEMENT,
                quantity=qty,
                reference=request.data.get("reference", ""),
                notes=request.data.get("notes", ""),
                created_by=request.user,
            )
            obj.receiving_location = location
            obj.save(update_fields=["receiving_location", "updated"])
            obj.close_if_resolved()
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)

    return Response({"return": _return_dict(obj, detail=True), "received_stock_item": received.pk}, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resolve(request, pk, line_pk):
    obj = get_object_or_404(SupplierReturn, pk=pk)
    line = get_object_or_404(SupplierReturnLine, pk=line_pk, supplier_return=obj)
    qty = _decimal(request.data.get("quantity"))
    if qty > line.outstanding_quantity:
        return Response({"detail": "Resolution quantity exceeds outstanding quantity"}, status=400)

    resolution_type = request.data.get("resolution_type")
    if resolution_type not in {SupplierReturn.Resolution.CREDIT, SupplierReturn.Resolution.REFUND, SupplierReturn.Resolution.OTHER}:
        return Response({"detail": "Use Receive Items for replacement or rework resolutions"}, status=400)

    amount = request.data.get("amount") or None
    SupplierReturnResolution.objects.create(
        line=line,
        resolution_type=resolution_type,
        quantity=qty,
        amount=amount,
        reference=request.data.get("reference", ""),
        notes=request.data.get("notes", ""),
        created_by=request.user,
    )
    obj.close_if_resolved()
    return Response(_return_dict(obj, detail=True), status=201)
