"""InvenTree Supplier Return plugin - V0.5.11."""
from decimal import Decimal, InvalidOperation
import json

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.urls import path
from django.utils.translation import gettext_lazy as _
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods
from plugin import InvenTreePlugin
from plugin.mixins import AppMixin, SettingsMixin, UrlsMixin, UserInterfaceMixin


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return {}


def _stock_po(stock):
    for name in ('purchase_order', 'purchaseorder'):
        value = getattr(stock, name, None)
        if value is not None:
            return value
    line = getattr(stock, 'purchase_order_line', None) or getattr(stock, 'purchaseorderlineitem', None)
    if line:
        return getattr(line, 'order', None) or getattr(line, 'purchase_order', None)
    return None


def _qty(value):
    """Human-friendly decimal string (300, 1.25; never 3E+2)."""
    try:
        d = Decimal(value)
        s = format(d, 'f')
        return s.rstrip('0').rstrip('.') if '.' in s else s
    except Exception:
        return str(value)


def _serialize(obj):
    supplier_name = ''
    try:
        from order.models import PurchaseOrder
        po = PurchaseOrder.objects.select_related('supplier').get(pk=obj.purchase_order_id)
        supplier_name = str(po.supplier) if po.supplier else ''
    except Exception:
        pass
    return {
        'id': obj.pk,
        'reference': obj.reference,
        'purchase_order_id': obj.purchase_order_id,
        'supplier_name': supplier_name,
        'supplier_rma': obj.supplier_rma,
        'status': obj.status,
        'holding_location_id': obj.holding_location_id,
        'external_location_id': obj.external_location_id,
        'shipment_date': obj.shipment_date.isoformat() if obj.shipment_date else None,
        'carrier': obj.carrier,
        'tracking_number': obj.tracking_number,
        'shipment_notes': obj.shipment_notes,
        'redmine_issue': obj.redmine_issue,
        'notes': obj.notes,
        'created_at': obj.created_at.isoformat(),
        'lines': [
            {
                'id': x.pk,
                'stock_item_id': x.stock_item_id,
                'return_stock_item_id': x.return_stock_item_id,
                'original_location_id': x.original_location_id,
                'purchase_order_line_id': x.purchase_order_line_id,
                'quantity': _qty(x.quantity),
                'reason': x.reason,
                'requested_resolution': x.requested_resolution,
                'notes': x.notes,
                'actual_resolutions': [
                    {
                        'id': r.pk,
                        'resolution': r.resolution,
                        'quantity': _qty(r.quantity),
                        'replacement_stock_item_id': r.replacement_stock_item_id,
                        'reference': r.reference,
                        'resolution_date': r.resolution_date.isoformat() if r.resolution_date else None,
                        'amount': str(r.amount) if r.amount is not None else None,
                        'notes': r.notes,
                        'received_quantity': _qty(sum((z.quantity for z in r.receipts.all()), Decimal('0'))),
                        'receipts': [
                            {
                                'id': z.pk, 'quantity': _qty(z.quantity),
                                'stock_item_id': z.stock_item_id, 'location_id': z.location_id,
                                'notes': z.notes, 'received_at': z.received_at.isoformat(),
                            } for z in r.receipts.all()
                        ],
                    }
                    for r in x.actual_resolutions.all()
                ],
            }
            for x in obj.lines.all()
        ],
    }


def _validate_lines(po_id, lines, exclude_return_id=None):
    from .models import SupplierReturnLine
    from stock.models import StockItem

    if not lines:
        raise ValueError('At least one return line is required.')

    validated = []
    seen = set()
    for raw in lines:
        try:
            stock_id = int(raw.get('stock_item_id'))
            stock = StockItem.objects.get(pk=stock_id)
            qty = Decimal(str(raw.get('quantity')))
        except (StockItem.DoesNotExist, ValueError, TypeError, InvalidOperation):
            raise ValueError('Invalid stock item or quantity.')

        if stock_id in seen:
            raise ValueError(f'Stock #{stock_id} can only appear once in a Supplier Return.')
        seen.add(stock_id)

        if qty <= 0 or qty > stock.quantity:
            raise ValueError(f'Return quantity for stock #{stock.pk} must be greater than zero and no more than {_qty(stock.quantity)}.')

        stock_po = _stock_po(stock)
        if not stock_po or stock_po.pk != po_id:
            raise ValueError(f'Stock #{stock.pk} did not originate from PO #{po_id}.')

        committed_qs = SupplierReturnLine.objects.filter(
            stock_item_id=stock.pk,
            supplier_return__status__in=['DRAFT', 'READY', 'SHIPPED'],
        )
        if exclude_return_id:
            committed_qs = committed_qs.exclude(supplier_return_id=exclude_return_id)
        committed = sum((x.quantity for x in committed_qs), Decimal('0'))
        if committed + qty > stock.quantity:
            raise ValueError(f'Stock #{stock.pk} does not have enough uncommitted quantity for this return.')

        reason = raw.get('reason')
        resolution = raw.get('requested_resolution')
        if reason not in SupplierReturnLine.Reason.values or resolution not in SupplierReturnLine.Resolution.values:
            raise ValueError('A valid reason and requested resolution are required.')
        validated.append((stock, qty, reason, resolution, raw.get('notes', '')))
    return validated


def _apply_draft(obj, data, validated):
    """Update an existing DRAFT in-place."""
    from .models import SupplierReturnLine

    obj.supplier_rma = data.get('supplier_rma', '')
    obj.holding_location_id = data.get('holding_location_id') or None
    obj.redmine_issue = data.get('redmine_issue', '')
    obj.notes = data.get('notes', '')
    obj.save(update_fields=['supplier_rma', 'holding_location_id', 'redmine_issue', 'notes', 'updated_at'])

    obj.lines.all().delete()
    for stock, qty, reason, resolution, notes in validated:
        line = getattr(stock, 'purchase_order_line', None)
        SupplierReturnLine.objects.create(
            supplier_return=obj,
            purchase_order_line_id=getattr(line, 'pk', None),
            stock_item_id=stock.pk,
            quantity=qty,
            reason=reason,
            requested_resolution=resolution,
            notes=notes,
        )


@require_http_methods(['GET'])
def context_view(request, model, pk):
    from .models import SupplierReturn
    from stock.models import StockItem

    if model == 'purchaseorder':
        po_id, stock_id = pk, None
    elif model == 'stockitem':
        try:
            stock = StockItem.objects.get(pk=pk)
        except StockItem.DoesNotExist:
            return JsonResponse({'error': 'Stock item not found'}, status=404)
        po = _stock_po(stock)
        if not po:
            return JsonResponse({'error': 'This stock item is not linked to an originating purchase order.'}, status=400)
        po_id, stock_id = po.pk, stock.pk
    else:
        return JsonResponse({'error': 'Unsupported context'}, status=400)

    returns = [
        _serialize(x)
        for x in SupplierReturn.objects.filter(purchase_order_id=po_id).prefetch_related('lines__actual_resolutions__receipts')
    ]

    eligible = []
    try:
        stocks = StockItem.objects.filter(purchase_order_id=po_id).select_related('part', 'location')
    except Exception:
        stocks = StockItem.objects.none()

    for item in stocks:
        part = getattr(item, 'part', None)
        eligible.append({
            'id': item.pk,
            'part': getattr(part, 'name', '') or getattr(part, 'IPN', '') or str(getattr(item, 'part_id', '')),
            'quantity': _qty(item.quantity),
            'serial': getattr(item, 'serial', None),
            'batch': getattr(item, 'batch', None),
            'location': str(getattr(item, 'location', '') or ''),
            'location_id': getattr(item, 'location_id', None),
        })

    return JsonResponse({
        'purchase_order_id': po_id,
        'preselected_stock_item_id': stock_id,
        'returns': returns,
        'eligible_stock': eligible,
    })


@require_http_methods(['GET', 'POST'])
def returns_view(request):
    from .models import SupplierReturn, SupplierReturnEvent
    from order.models import PurchaseOrder

    if request.method == 'GET':
        po_id = request.GET.get('purchase_order_id')
        qs = SupplierReturn.objects.all().prefetch_related('lines__actual_resolutions__receipts')
        if po_id:
            qs = qs.filter(purchase_order_id=po_id)
        return JsonResponse({'results': [_serialize(x) for x in qs]})

    data = _json_body(request)
    try:
        po_id = int(data.get('purchase_order_id'))
    except Exception:
        return JsonResponse({'error': 'A purchase order is required.'}, status=400)

    if not PurchaseOrder.objects.filter(pk=po_id).exists():
        return JsonResponse({'error': 'Purchase order not found.'}, status=404)

    try:
        validated = _validate_lines(po_id, data.get('lines') or [])
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    with transaction.atomic():
        obj = SupplierReturn.objects.create(
            purchase_order_id=po_id,
            created_by=request.user if request.user.is_authenticated else None,
        )
        _apply_draft(obj, data, validated)
        SupplierReturnEvent.objects.create(
            supplier_return=obj,
            event_type='CREATED',
            user=request.user if request.user.is_authenticated else None,
            notes='Supplier Return draft created',
        )
    return JsonResponse(_serialize(obj), status=201)


@require_http_methods(['GET', 'PATCH'])
def return_detail_view(request, pk):
    from .models import SupplierReturn, SupplierReturnEvent
    from stock.models import StockItem, StockLocation

    try:
        obj = SupplierReturn.objects.prefetch_related('lines__actual_resolutions__receipts').get(pk=pk)
    except SupplierReturn.DoesNotExist:
        return JsonResponse({'error': 'Supplier Return not found.'}, status=404)

    if request.method == 'GET':
        return JsonResponse(_serialize(obj))

    data = _json_body(request)
    action = data.get('action')

    # DRAFT editing: everything remains editable and no stock changes occur.
    if action == 'save_draft':
        if obj.status != 'DRAFT':
            return JsonResponse({'error': 'Only a Draft Supplier Return can be fully edited.'}, status=400)
        try:
            validated = _validate_lines(obj.purchase_order_id, data.get('lines') or [], exclude_return_id=obj.pk)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        with transaction.atomic():
            _apply_draft(obj, data, validated)
            SupplierReturnEvent.objects.create(
                supplier_return=obj,
                event_type='DRAFT_UPDATED',
                user=request.user if request.user.is_authenticated else None,
                notes='Supplier Return draft updated',
            )
        obj.refresh_from_db()
        return JsonResponse(_serialize(obj))

    # READY: physically segregate the selected quantities into the holding location.
    if action == 'mark_ready':
        if obj.status != 'DRAFT':
            return JsonResponse({'error': 'Only a Draft Supplier Return can be marked Ready to Return.'}, status=400)
        holding_id = data.get('holding_location_id') or obj.holding_location_id
        if not holding_id:
            return JsonResponse({'error': 'A holding location is required before stock can be marked Ready to Return.'}, status=400)
        try:
            holding = StockLocation.objects.get(pk=int(holding_id))
        except (StockLocation.DoesNotExist, TypeError, ValueError):
            return JsonResponse({'error': 'The selected holding location is invalid.'}, status=400)

        user = request.user if request.user.is_authenticated else None
        try:
            with transaction.atomic():
                # Lock the SR and stock rows to prevent double-commit / concurrent quantity changes.
                obj = SupplierReturn.objects.select_for_update().get(pk=obj.pk)
                if obj.status != 'DRAFT':
                    raise ValueError('This Supplier Return is no longer a Draft.')
                lines = list(obj.lines.select_for_update())
                if not lines:
                    raise ValueError('At least one return line is required.')

                # Revalidate all quantities immediately before changing stock.
                locked = []
                for line in lines:
                    stock = StockItem.objects.select_for_update().get(pk=line.stock_item_id)
                    if line.quantity <= 0 or line.quantity > stock.quantity:
                        raise ValueError(f'Stock #{stock.pk} no longer has {_qty(line.quantity)} available for this return.')
                    stock_po = _stock_po(stock)
                    if not stock_po or stock_po.pk != obj.purchase_order_id:
                        raise ValueError(f'Stock #{stock.pk} is no longer linked to the expected purchase order.')
                    locked.append((line, stock))

                for line, stock in locked:
                    line.original_location_id = stock.location_id
                    note = f'{obj.reference}: segregated for supplier return'
                    if line.quantity < stock.quantity:
                        returned_stock = stock.splitStock(line.quantity, holding, user, notes=note)
                        if returned_stock is None or returned_stock.pk == stock.pk:
                            raise ValueError(f'Could not split Stock #{stock.pk} for the supplier return.')
                    else:
                        ok = stock.move(holding, note, user, quantity=line.quantity)
                        if ok is False:
                            raise ValueError(f'Could not move Stock #{stock.pk} to the holding location.')
                        returned_stock = stock

                    line.return_stock_item_id = returned_stock.pk
                    line.save(update_fields=['original_location_id', 'return_stock_item_id'])

                obj.holding_location_id = holding.pk
                obj.status = 'READY'
                obj.save(update_fields=['holding_location_id', 'status', 'updated_at'])
                SupplierReturnEvent.objects.create(
                    supplier_return=obj,
                    event_type='STATUS_READY',
                    user=user,
                    notes=f'Stock segregated to holding location #{holding.pk}',
                )
        except (ValueError, DjangoValidationError) as exc:
            message = getattr(exc, 'message', None) or '; '.join(getattr(exc, 'messages', [])) or str(exc)
            return JsonResponse({'error': message}, status=400)

        obj = SupplierReturn.objects.prefetch_related('lines__actual_resolutions__receipts').get(pk=obj.pk)
        return JsonResponse(_serialize(obj))

    # SHIPPED: move all segregated return stock to a user-selected external location.
    if action == 'mark_shipped':
        if obj.status != 'READY':
            return JsonResponse({'error': 'Only a Ready to Return Supplier Return can be marked Shipped.'}, status=400)

        external_id = data.get('external_location_id')
        if not external_id:
            return JsonResponse({'error': 'An external supplier location is required.'}, status=400)
        try:
            external = StockLocation.objects.get(pk=int(external_id))
        except (StockLocation.DoesNotExist, TypeError, ValueError):
            return JsonResponse({'error': 'The selected external supplier location is invalid.'}, status=400)

        raw_date = data.get('shipment_date')
        shipment_date = parse_date(raw_date) if raw_date else None
        if raw_date and shipment_date is None:
            return JsonResponse({'error': 'Shipment date is invalid.'}, status=400)

        carrier = (data.get('carrier') or '').strip()
        tracking = (data.get('tracking_number') or '').strip()
        shipment_notes = (data.get('shipment_notes') or '').strip()
        user = request.user if request.user.is_authenticated else None

        try:
            with transaction.atomic():
                obj = SupplierReturn.objects.select_for_update().get(pk=obj.pk)
                if obj.status != 'READY':
                    raise ValueError('This Supplier Return is no longer Ready to Return.')
                lines = list(obj.lines.select_for_update())
                if not lines:
                    raise ValueError('At least one return line is required.')

                locked = []
                for line in lines:
                    if not line.return_stock_item_id:
                        raise ValueError(f'Return stock has not been prepared for line #{line.pk}.')
                    stock = StockItem.objects.select_for_update().get(pk=line.return_stock_item_id)
                    if stock.quantity < line.quantity:
                        raise ValueError(f'Return Stock #{stock.pk} no longer contains the expected {_qty(line.quantity)} units.')
                    locked.append((line, stock))

                for line, stock in locked:
                    note = f'{obj.reference}: shipped to supplier / external location'
                    ok = stock.move(external, note, user, quantity=line.quantity)
                    if ok is False:
                        raise ValueError(f'Could not move Return Stock #{stock.pk} to the external location.')

                obj.external_location_id = external.pk
                obj.shipment_date = shipment_date
                obj.carrier = carrier
                obj.tracking_number = tracking
                obj.shipment_notes = shipment_notes
                obj.status = 'SHIPPED'
                obj.save(update_fields=[
                    'external_location_id', 'shipment_date', 'carrier', 'tracking_number',
                    'shipment_notes', 'status', 'updated_at'
                ])
                detail = f'Shipped return stock to external location #{external.pk}'
                if carrier:
                    detail += f' via {carrier}'
                if tracking:
                    detail += f' (tracking {tracking})'
                SupplierReturnEvent.objects.create(
                    supplier_return=obj, event_type='STATUS_SHIPPED', user=user, notes=detail
                )
        except (ValueError, DjangoValidationError, StockItem.DoesNotExist) as exc:
            message = getattr(exc, 'message', None) or '; '.join(getattr(exc, 'messages', [])) or str(exc)
            return JsonResponse({'error': message}, status=400)

        obj = SupplierReturn.objects.prefetch_related('lines__actual_resolutions__receipts').get(pk=obj.pk)
        return JsonResponse(_serialize(obj))

    # After READY, requested resolution / admin fields may still evolve. Returned stock and qty stay locked.
    if action == 'update_admin':
        if obj.status not in {'READY', 'SHIPPED', 'RESOLUTION'}:
            return JsonResponse({'error': 'Administrative updates are available after the return is Ready to Return.'}, status=400)
        obj.supplier_rma = data.get('supplier_rma', obj.supplier_rma)
        obj.redmine_issue = data.get('redmine_issue', obj.redmine_issue)
        obj.notes = data.get('notes', obj.notes)
        requested = data.get('requested_resolutions') or {}
        with transaction.atomic():
            obj.save(update_fields=['supplier_rma', 'redmine_issue', 'notes', 'updated_at'])
            for line in obj.lines.all():
                value = requested.get(str(line.pk), requested.get(line.pk))
                if value:
                    from .models import SupplierReturnLine
                    if value not in SupplierReturnLine.Resolution.values:
                        return JsonResponse({'error': 'Invalid requested resolution.'}, status=400)
                    line.requested_resolution = value
                    line.save(update_fields=['requested_resolution'])
            SupplierReturnEvent.objects.create(
                supplier_return=obj,
                event_type='ADMIN_UPDATED',
                user=request.user if request.user.is_authenticated else None,
                notes='Supplier Return administrative details updated',
            )
        return JsonResponse(_serialize(obj))

    return JsonResponse({'error': 'Unknown Supplier Return action.'}, status=400)


@require_http_methods(['POST'])
def resolution_view(request, pk):
    """Record a quantity-level actual supplier resolution."""
    from .models import SupplierReturn, SupplierReturnEvent, SupplierReturnLine, SupplierReturnResolution
    from stock.models import StockItem

    try:
        obj = SupplierReturn.objects.prefetch_related('lines__actual_resolutions__receipts').get(pk=pk)
    except SupplierReturn.DoesNotExist:
        return JsonResponse({'error': 'Supplier Return not found.'}, status=404)
    if obj.status not in {'SHIPPED', 'RESOLUTION'}:
        return JsonResponse({'error': 'Actual resolution can only be recorded after the return has been shipped.'}, status=400)

    data = _json_body(request)
    try:
        line = obj.lines.get(pk=int(data.get('line_id')))
        qty = Decimal(str(data.get('quantity')))
    except (SupplierReturnLine.DoesNotExist, ValueError, TypeError, InvalidOperation):
        return JsonResponse({'error': 'A valid return line and quantity are required.'}, status=400)
    resolution = data.get('resolution')
    if resolution not in SupplierReturnResolution.Resolution.values:
        return JsonResponse({'error': 'A valid actual resolution is required.'}, status=400)
    if qty <= 0:
        return JsonResponse({'error': 'Resolution quantity must be greater than zero.'}, status=400)
    notes = (data.get('notes') or '').strip()
    if resolution == 'OTHER' and not notes:
        return JsonResponse({'error': 'Notes are required when Actual Resolution is Other.'}, status=400)
    already = sum((r.quantity for r in line.actual_resolutions.all()), Decimal('0'))
    if already + qty > line.quantity:
        return JsonResponse({'error': f'Only {_qty(line.quantity - already)} remains unresolved on this line.'}, status=400)

    raw_date = data.get('resolution_date')
    resolution_date = parse_date(raw_date) if raw_date else None
    if raw_date and resolution_date is None:
        return JsonResponse({'error': 'Resolution date is invalid.'}, status=400)
    amount = data.get('amount')
    if amount in ('', None):
        amount = None
    else:
        try:
            amount = Decimal(str(amount))
        except InvalidOperation:
            return JsonResponse({'error': 'Amount is invalid.'}, status=400)

    user = request.user if request.user.is_authenticated else None
    try:
        with transaction.atomic():
            obj = SupplierReturn.objects.select_for_update().get(pk=obj.pk)
            line = SupplierReturnLine.objects.select_for_update().get(pk=line.pk)
            already = sum((r.quantity for r in line.actual_resolutions.all()), Decimal('0'))
            if already + qty > line.quantity:
                raise ValueError('The unresolved quantity changed. Reload and try again.')
            r = SupplierReturnResolution.objects.create(
                line=line, resolution=resolution, quantity=qty,
                resolution_date=resolution_date, reference=(data.get('reference') or '').strip(),
                amount=amount, notes=notes, created_by=user,
            )
            # A credit/refund is a completed disposition: the supplier retains the physical material.
            if resolution in {'CREDIT', 'REFUND'}:
                stock = StockItem.objects.select_for_update().get(pk=line.return_stock_item_id)
                if qty > stock.quantity:
                    raise ValueError(f'Return Stock #{stock.pk} only has {_qty(stock.quantity)} remaining at the supplier.')
                ok = stock.take_stock(qty, user, notes=f'{obj.reference}: {resolution.lower()} resolved by supplier')
                if ok is False and qty < stock.quantity:
                    raise ValueError(f'Could not remove resolved quantity from Return Stock #{stock.pk}.')
            obj.status = 'RESOLUTION'
            obj.save(update_fields=['status', 'updated_at'])
            SupplierReturnEvent.objects.create(
                supplier_return=obj, event_type='RESOLUTION_RECORDED', user=user,
                notes=f'{_qty(qty)} recorded as {resolution} on line #{line.pk}',
            )
    except (ValueError, DjangoValidationError, StockItem.DoesNotExist) as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    obj = SupplierReturn.objects.prefetch_related('lines__actual_resolutions__receipts').get(pk=obj.pk)
    return JsonResponse(_serialize(obj), status=201)


@require_http_methods(['DELETE'])
def resolution_delete_view(request, pk, resolution_pk):
    """Reverse an actual resolution only when no irreversible downstream action has occurred."""
    from .models import SupplierReturn, SupplierReturnEvent, SupplierReturnResolution

    try:
        obj = SupplierReturn.objects.prefetch_related('lines__actual_resolutions__receipts').get(pk=pk)
        res = SupplierReturnResolution.objects.select_related('line').prefetch_related('receipts').get(
            pk=resolution_pk, line__supplier_return=obj
        )
    except (SupplierReturn.DoesNotExist, SupplierReturnResolution.DoesNotExist):
        return JsonResponse({'error': 'Supplier Return resolution not found.'}, status=404)

    if obj.status == 'CLOSED':
        return JsonResponse({'error': 'Closed Supplier Returns cannot be changed.'}, status=400)
    if res.receipts.exists() or res.replacement_stock_item_id:
        return JsonResponse({'error': 'This resolution cannot be reversed because material has already been received against it.'}, status=400)
    if res.resolution in {'CREDIT', 'REFUND'}:
        return JsonResponse({'error': 'Credit / refund resolutions cannot be reversed because inventory was already removed. Create a correcting transaction instead.'}, status=400)

    qty, kind, line_pk = res.quantity, res.resolution, res.line_id
    with transaction.atomic():
        res.delete()
        SupplierReturnEvent.objects.create(
            supplier_return=obj, event_type='RESOLUTION_REVERSED',
            user=request.user if request.user.is_authenticated else None,
            notes=f'{_qty(qty)} {kind} resolution reversed on line #{line_pk}',
        )
        remaining = any(line.actual_resolutions.exists() for line in obj.lines.all())
        obj.status = 'RESOLUTION' if remaining else 'SHIPPED'
        obj.save(update_fields=['status', 'updated_at'])

    obj = SupplierReturn.objects.prefetch_related('lines__actual_resolutions__receipts').get(pk=obj.pk)
    return JsonResponse(_serialize(obj))


@require_http_methods(['POST'])
def receipt_view(request, pk, resolution_pk):
    """Receive physical replacement or reworked material against an actual resolution."""
    from .models import SupplierReturn, SupplierReturnEvent, SupplierReturnReceipt, SupplierReturnResolution
    from stock.models import StockItem, StockLocation

    try:
        obj = SupplierReturn.objects.get(pk=pk)
        res = SupplierReturnResolution.objects.select_related('line').get(pk=resolution_pk, line__supplier_return=obj)
    except (SupplierReturn.DoesNotExist, SupplierReturnResolution.DoesNotExist):
        return JsonResponse({'error': 'Supplier Return resolution not found.'}, status=404)
    if res.resolution not in {'REPLACEMENT', 'REWORK'}:
        return JsonResponse({'error': 'Only replacement or repair/rework resolutions have physical receipts.'}, status=400)
    data = _json_body(request)
    try:
        qty = Decimal(str(data.get('quantity')))
        location = StockLocation.objects.get(pk=int(data.get('location_id')))
    except (InvalidOperation, TypeError, ValueError, StockLocation.DoesNotExist):
        return JsonResponse({'error': 'A valid quantity and receiving location are required.'}, status=400)
    received = sum((x.quantity for x in res.receipts.all()), Decimal('0'))
    if qty <= 0 or received + qty > res.quantity:
        return JsonResponse({'error': f'Receipt quantity must be greater than zero and no more than {_qty(res.quantity - received)}.'}, status=400)

    user = request.user if request.user.is_authenticated else None
    notes = (data.get('notes') or '').strip()
    batch = (data.get('batch') or '').strip()
    try:
        stock_status = int(data.get('status', 50))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'A valid stock status is required.'}, status=400)
    try:
        with transaction.atomic():
            res = SupplierReturnResolution.objects.select_for_update().select_related('line').get(pk=res.pk)
            received = sum((x.quantity for x in res.receipts.all()), Decimal('0'))
            if received + qty > res.quantity:
                raise ValueError('The outstanding receipt quantity changed. Reload and try again.')
            return_stock = StockItem.objects.select_for_update().get(pk=res.line.return_stock_item_id)
            if qty > return_stock.quantity:
                raise ValueError(f'Return Stock #{return_stock.pk} only has {_qty(return_stock.quantity)} remaining at the supplier.')

            if res.resolution == 'REWORK':
                # Same physical material comes back; preserve stock identity when the whole remainder returns.
                if qty < return_stock.quantity:
                    received_stock = return_stock.splitStock(qty, location, user, notes=f'{obj.reference}: repaired/reworked material received')
                else:
                    ok = return_stock.move(location, f'{obj.reference}: repaired/reworked material received', user, quantity=qty)
                    if ok is False:
                        raise ValueError('Could not move reworked material to the receiving location.')
                    received_stock = return_stock
                old_batch = getattr(received_stock, 'batch', None) or ''
                received_stock.batch = batch
                received_stock.status = stock_status
                received_stock.save(update_fields=['batch', 'status', 'updated'])
                from stock.status_codes import StockHistoryCode
                received_stock.add_tracking_entry(
                    StockHistoryCode.STOCK_UPDATE,
                    user,
                    notes=(
                        f'{obj.reference}: repaired/reworked material received; '
                        f'Batch ID changed from {old_batch or "<blank>"} to {batch or "<blank>"}; '
                        f'stock status set to {_stock_status_label(stock_status)}'
                    ),
                    deltas={
                        'batch': batch,
                        'status': stock_status,
                        'supplier_return': obj.reference,
                        'source_stock_item': return_stock.pk,
                    },
                )
            else:
                # Replacement is new physical material. Do not receive it against the original PO.
                old_batch = getattr(return_stock, 'batch', None) or ''
                kwargs = {
                    'part_id': return_stock.part_id,
                    'quantity': qty,
                    'location': location,
                    'batch': batch,
                    'status': stock_status,
                    'supplier_part_id': getattr(return_stock, 'supplier_part_id', None),
                    'purchase_price': getattr(return_stock, 'purchase_price', None),
                    'purchase_price_currency': getattr(return_stock, 'purchase_price_currency', None),
                }
                # Drop None values so model defaults are respected.
                received_stock = StockItem.objects.create(**{k:v for k,v in kwargs.items() if v is not None})
                tracking_note = (
                    f'{obj.reference}: replacement stock received; '
                    f'Batch ID changed from {old_batch or "<blank>"} to {batch or "<blank>"}; '
                    f'stock status set to {_stock_status_label(stock_status)}'
                )
                # Add an explicit native InvenTree stock tracking entry. Creating a
                # StockItem only records its initial state; a zero-quantity add is ignored
                # by current InvenTree versions. The STOCK_UPDATE entry below preserves
                # the Supplier Return provenance, batch transition and selected status.
                from stock.status_codes import StockHistoryCode
                received_stock.add_tracking_entry(
                    StockHistoryCode.STOCK_UPDATE,
                    user,
                    notes=tracking_note,
                    deltas={
                        'batch': batch,
                        'status': stock_status,
                        'supplier_return': obj.reference,
                        'source_stock_item': return_stock.pk,
                    },
                )
                ok = return_stock.take_stock(qty, user, notes=f'{obj.reference}: replaced by Stock #{received_stock.pk}')
                if ok is False and qty < return_stock.quantity:
                    raise ValueError('Could not reduce returned stock after replacement receipt.')

            SupplierReturnReceipt.objects.create(
                resolution=res, quantity=qty, stock_item_id=received_stock.pk,
                location_id=location.pk, notes=notes, created_by=user,
            )
            res.replacement_stock_item_id = received_stock.pk
            res.save(update_fields=['replacement_stock_item_id'])
            SupplierReturnEvent.objects.create(
                supplier_return=obj, event_type='RESOLUTION_RECEIVED', user=user,
                notes=(
                    f'Received {_qty(qty)} for {res.resolution} as Stock #{received_stock.pk}; '
                    f'Batch ID {batch or "<blank>"}; stock status {_stock_status_label(stock_status)}'
                ),
            )
    except (ValueError, DjangoValidationError, StockItem.DoesNotExist) as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    obj = SupplierReturn.objects.prefetch_related('lines__actual_resolutions__receipts').get(pk=obj.pk)
    return JsonResponse(_serialize(obj), status=201)


def _stock_status_label(value):
    """Return the human-readable label for a built-in InvenTree stock status."""
    labels = {
        10: 'OK',
        50: 'Attention needed',
        55: 'Damaged',
        60: 'Destroyed',
        65: 'Rejected',
        70: 'Lost',
        75: 'Quarantined',
        85: 'Returned',
    }
    try:
        return labels.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value)


@require_http_methods(['POST'])
def close_return_view(request, pk):
    from .models import SupplierReturn, SupplierReturnEvent
    try:
        obj = SupplierReturn.objects.prefetch_related('lines__actual_resolutions__receipts').get(pk=pk)
    except SupplierReturn.DoesNotExist:
        return JsonResponse({'error': 'Supplier Return not found.'}, status=404)
    for line in obj.lines.all():
        resolved = sum((r.quantity for r in line.actual_resolutions.all()), Decimal('0'))
        if resolved != line.quantity:
            return JsonResponse({'error': f'Line #{line.pk} is not fully resolved ({_qty(resolved)} / {_qty(line.quantity)}).'}, status=400)
        for r in line.actual_resolutions.all():
            if r.resolution in {'REPLACEMENT', 'REWORK'}:
                received = sum((x.quantity for x in r.receipts.all()), Decimal('0'))
                if received != r.quantity:
                    return JsonResponse({'error': f'{r.get_resolution_display()} is not fully received ({_qty(received)} / {_qty(r.quantity)}).'}, status=400)
    obj.status = 'CLOSED'
    obj.save(update_fields=['status', 'updated_at'])
    SupplierReturnEvent.objects.create(
        supplier_return=obj, event_type='STATUS_CLOSED',
        user=request.user if request.user.is_authenticated else None,
        notes='Supplier Return fully resolved and closed',
    )
    return JsonResponse(_serialize(obj))


def supplier_return_queue_page(request):
    """Render the central Supplier Returns operational queue."""
    if not getattr(request.user, 'is_authenticated', False):
        from django.shortcuts import redirect
        return redirect('/accounts/login/?next=' + request.path)

    from .models import SupplierReturn
    import html

    returns = SupplierReturn.objects.prefetch_related(
        'lines__actual_resolutions__receipts'
    ).order_by('-created_at')

    rows = []
    statuses = set()
    for obj in returns:
        data = _serialize(obj)
        total = sum((Decimal(str(line['quantity'])) for line in data['lines']), Decimal('0'))
        resolved = sum((sum((Decimal(str(r['quantity'])) for r in line.get('actual_resolutions', [])), Decimal('0')) for line in data['lines']), Decimal('0'))
        received = sum((sum((Decimal(str(r.get('received_quantity') or '0')) for r in line.get('actual_resolutions', [])), Decimal('0')) for line in data['lines']), Decimal('0'))
        status_label = {'READY':'Ready to Return','SHIPPED':'Awaiting Resolution','RESOLUTION':'Resolution in Progress','CLOSED':'Closed','CANCELLED':'Cancelled','DRAFT':'Draft'}.get(data['status'], data['status'].replace('_', ' ').title())
        statuses.add((data['status'], status_label))
        rows.append({**data, 'returned':_qty(total), 'resolved':_qty(resolved), 'outstanding':_qty(max(Decimal('0'), total-resolved)), 'received':_qty(received), 'status_label':status_label})

    def e(v):
        return html.escape(str(v or ''))

    row_html = ''.join(
        '<tr data-status="{status}" data-search="{search}">'
        '<td><b>{ref}</b></td><td>{supplier}</td>'
        '<td><a href="/web/purchasing/purchase-order/{po}/supplier-return-panel">PO #{po}</a></td>'
        '<td>{rma}</td><td><b>{status_label}</b></td>'
        '<td>{returned}</td><td>{resolved}</td><td>{outstanding}</td><td>{received}</td>'
        '<td>{created}</td><td>{shipped}</td>'
        '<td><a href="/web/purchasing/purchase-order/{po}/supplier-return-panel">Open</a></td></tr>'.format(
            status=e(r['status']), search=e((r['reference']+' '+(r['supplier_name'] or '')+' '+(r['supplier_rma'] or '')+' PO-'+str(r['purchase_order_id'])+' '+' '.join(str(ar.get('resolution') or ar.get('resolution_type') or ar.get('actual_resolution') or '') for line in r.get('lines', []) for ar in line.get('actual_resolutions', []))).lower()),
            ref=e(r['reference']), supplier=e(r['supplier_name']) or '—', po=r['purchase_order_id'], rma=e(r['supplier_rma']) or '—',
            status_label=e(r['status_label']), returned=e(r['returned']), resolved=e(r['resolved']), outstanding=e(r['outstanding']), received=e(r['received']),
            created=e((r['created_at'] or '')[:10]), shipped=e(r['shipment_date']) or '—')
        for r in rows
    ) or '<tr><td colspan="12">No Supplier Returns found.</td></tr>'

    status_options = ''.join('<option value="{}">{}</option>'.format(e(k),e(v)) for k,v in sorted(statuses, key=lambda x:x[1]))
    supplier_names = sorted({r['supplier_name'] for r in rows if r.get('supplier_name')})
    supplier_options = ''.join('<option value="{}">{}</option>'.format(e(v.lower()), e(v)) for v in supplier_names)
    resolution_values = sorted({str(ar.get('resolution') or ar.get('resolution_type') or ar.get('actual_resolution') or '').strip()
                                for r in rows for line in r.get('lines', []) for ar in line.get('actual_resolutions', [])
                                if str(ar.get('resolution') or ar.get('resolution_type') or ar.get('actual_resolution') or '').strip()})
    resolution_options = ''.join('<option value="{}">{}</option>'.format(e(v.lower()), e(v.replace('_',' ').title())) for v in resolution_values)
    page = """<!doctype html><html><head><meta charset="utf-8"><title>Supplier Returns - InvenTree</title>
<style>body{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0;background:#f8f9fa;color:#212529}header{background:#fff;border-bottom:1px solid #ddd;padding:14px 24px;display:flex;align-items:center;justify-content:space-between}main{padding:24px}h1{margin:0 0 4px;font-size:26px}.sub{color:#666;margin:0 0 18px}.controls{display:flex;gap:10px;margin:14px 0;flex-wrap:wrap;align-items:end}.controls label{display:flex;flex-direction:column;gap:4px;font-size:12px;font-weight:600}.controls input,.controls select{padding:8px 10px;border:1px solid #bbb;border-radius:4px;background:white;min-width:145px}.controls button{padding:8px 12px;border:1px solid #aaa;border-radius:4px;background:white;cursor:pointer}table{width:100%;border-collapse:collapse;background:white;border:1px solid #ddd}th,td{padding:9px;border-bottom:1px solid #e5e5e5;text-align:left;white-space:nowrap}th{background:#f1f3f5}a{color:#1971c2;text-decoration:none}a:hover{text-decoration:underline}.back{font-weight:600}</style></head><body>
<header><div><b>InvenTree</b> / Supplier Returns</div><a class="back" href="/web/">Return to InvenTree</a></header>
<main><h1>Supplier Returns</h1><p class="sub">Operational queue for supplier returns, RMAs and outstanding resolutions.</p>
<div class="controls">
<label>Status<select id="status"><option value="">All</option><option value="__OPEN__">Open only</option>{status_options}</select></label>
<label>Supplier<select id="supplier"><option value="">All</option>{supplier_options}</select></label>
<label>Original PO<input id="po" placeholder="PO # / reference"></label>
<label>Supplier RMA<input id="rma" placeholder="RMA #"></label>
<label>Resolution<select id="resolution"><option value="">All</option>{resolution_options}</select></label>
<label>Created From<input id="createdFrom" type="date"></label><label>Created To<input id="createdTo" type="date"></label>
<label>Shipped From<input id="shippedFrom" type="date"></label><label>Shipped To<input id="shippedTo" type="date"></label>
<label>Search<input id="search" placeholder="SR / supplier / RMA / PO"></label><button id="clear" type="button">Clear Filters</button></div>
<div style="overflow:auto"><table><thead><tr><th>SR</th><th>Supplier</th><th>Original PO</th><th>Supplier RMA</th><th>Status</th><th>Returned</th><th>Resolved</th><th>Outstanding</th><th>Received</th><th>Created</th><th>Shipped</th><th></th></tr></thead><tbody id="rows">{row_html}</tbody></table></div></main>
<script>
const ids=['status','supplier','po','rma','resolution','createdFrom','createdTo','shippedFrom','shippedTo','search'];
const el=Object.fromEntries(ids.map(id=>[id,document.getElementById(id)]));
function filterRows(){const s=el.status.value,q=el.search.value.trim().toLowerCase(),sup=el.supplier.value,po=el.po.value.trim().toLowerCase(),rma=el.rma.value.trim().toLowerCase(),res=el.resolution.value,cf=el.createdFrom.value,ct=el.createdTo.value,sf=el.shippedFrom.value,st=el.shippedTo.value;document.querySelectorAll('#rows tr[data-status]').forEach(r=>{const cells=r.cells,search=(r.dataset.search||''),supplier=(cells[1]?.textContent||'').trim().toLowerCase(),pov=(cells[2]?.textContent||'').trim().toLowerCase(),rmav=(cells[3]?.textContent||'').trim().toLowerCase(),created=(cells[9]?.textContent||'').trim(),shipped=(cells[10]?.textContent||'').trim(),statusMatch=!s||(s==='__OPEN__'?!['CLOSED','CANCELLED'].includes(r.dataset.status):r.dataset.status===s),supplierMatch=!sup||supplier===sup,poMatch=!po||pov.includes(po),rmaMatch=!rma||rmav.includes(rma),createdMatch=(!cf||created>=cf)&&(!ct||created<=ct),shippedMatch=(!sf||(shipped!=='—'&&shipped>=sf))&&(!st||(shipped!=='—'&&shipped<=st)),searchMatch=!q||search.includes(q),resolutionMatch=!res||search.includes(res);r.style.display=statusMatch&&supplierMatch&&poMatch&&rmaMatch&&createdMatch&&shippedMatch&&searchMatch&&resolutionMatch?'':'none';});}
ids.forEach(id=>el[id].addEventListener(id==='search'||id==='po'||id==='rma'?'input':'change',filterRows));
document.getElementById('clear').addEventListener('click',()=>{ids.forEach(id=>el[id].value='');filterRows();});
</script></body></html>"""
    page = page.replace('{status_options}', status_options).replace('{supplier_options}', supplier_options).replace('{resolution_options}', resolution_options).replace('{row_html}', row_html)
    return HttpResponse(page)


class SupplierReturnPlugin(UrlsMixin, AppMixin, SettingsMixin, UserInterfaceMixin, InvenTreePlugin):
    NAME = 'SupplierReturn'
    SLUG = 'supplier-return'
    TITLE = 'Supplier Return'
    DESCRIPTION = 'Manage supplier returns, RMAs, replacements, credits, refunds and rework with purchase-order and stock traceability.'
    VERSION = '0.5.20'
    AUTHOR = 'Per Vices Corporation'
    WEBSITE = 'https://github.com/bmalatest-dev/inventree-supplier-return'
    LICENSE = 'MIT'

    def setup_urls(self):
        return [
            path('queue/', supplier_return_queue_page, name='queue'),
            path('context/<str:model>/<int:pk>/', context_view, name='context'),
            path('returns/', returns_view, name='returns'),
            path('returns/<int:pk>/', return_detail_view, name='return-detail'),
            path('returns/<int:pk>/resolutions/', resolution_view, name='resolution-create'),
            path('returns/<int:pk>/resolutions/<int:resolution_pk>/', resolution_delete_view, name='resolution-delete'),
            path('returns/<int:pk>/resolutions/<int:resolution_pk>/receive/', receipt_view, name='resolution-receive'),
            path('returns/<int:pk>/close/', close_return_view, name='return-close'),
        ]

    SETTINGS = {
        'DEFAULT_HOLDING_LOCATION': {'name': _('Default return holding location'), 'description': _('Optional default; the user can override it for each return.'), 'model': 'stock.stocklocation', 'required': False},
        'DEFAULT_EXTERNAL_LOCATION': {'name': _('Default supplier / external location'), 'description': _('Reserved for the shipping workflow.'), 'model': 'stock.stocklocation', 'required': False},
        'DEFAULT_RECEIVING_LOCATION': {'name': _('Default return receiving location'), 'description': _('Reserved for the receiving workflow.'), 'model': 'stock.stocklocation', 'required': False},
    }



    def get_ui_panels(self, request, context, **kwargs):
        context = context or {}
        target_model = context.get('target_model')
        target_id = context.get('target_id')
        if target_id is None or target_model not in {'purchaseorder', 'stockitem'}:
            return []
        return [{
            'key': 'supplier-return-panel',
            'title': _('Supplier Returns'),
            'description': _('Supplier returns and RMA activity for this record.'),
            'source': self.plugin_static_file('supplier_return_v054.js:renderSupplierReturnPanel'),
            'icon': 'ti:truck-return:outline',
            'context': {
                'target_model': target_model,
                'target_id': target_id,
                'plugin_version': self.VERSION,
                'plugin_base': f'/plugin/{self.SLUG}',
            },
        }]
