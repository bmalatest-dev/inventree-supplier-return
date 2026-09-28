"""InvenTree Supplier Return plugin - V0.2.2."""
from decimal import Decimal, InvalidOperation
import json

from django.http import JsonResponse
from django.urls import path
from django.utils.translation import gettext_lazy as _
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


def _serialize(obj):
    return {
        'id': obj.pk,
        'reference': obj.reference,
        'purchase_order_id': obj.purchase_order_id,
        'supplier_rma': obj.supplier_rma,
        'status': obj.status,
        'holding_location_id': obj.holding_location_id,
        'redmine_issue': obj.redmine_issue,
        'notes': obj.notes,
        'created_at': obj.created_at.isoformat(),
        'lines': [
            {
                'id': x.pk,
                'stock_item_id': x.stock_item_id,
                'purchase_order_line_id': x.purchase_order_line_id,
                'quantity': str(x.quantity.normalize()),
                'reason': x.reason,
                'requested_resolution': x.requested_resolution,
                'notes': x.notes,
            }
            for x in obj.lines.all()
        ],
    }


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
        for x in SupplierReturn.objects.filter(purchase_order_id=po_id).prefetch_related('lines')
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
            'quantity': str(item.quantity),
            'serial': getattr(item, 'serial', None),
            'batch': getattr(item, 'batch', None),
            'location': str(getattr(item, 'location', '') or ''),
        })

    return JsonResponse({
        'purchase_order_id': po_id,
        'preselected_stock_item_id': stock_id,
        'returns': returns,
        'eligible_stock': eligible,
    })


@require_http_methods(['GET', 'POST'])
def returns_view(request):
    from .models import SupplierReturn, SupplierReturnLine, SupplierReturnEvent

    if request.method == 'GET':
        po_id = request.GET.get('purchase_order_id')
        qs = SupplierReturn.objects.all().prefetch_related('lines')
        if po_id:
            qs = qs.filter(purchase_order_id=po_id)
        return JsonResponse({'results': [_serialize(x) for x in qs]})

    data = _json_body(request)
    try:
        po_id = int(data.get('purchase_order_id'))
    except Exception:
        return JsonResponse({'error': 'A purchase order is required.'}, status=400)

    lines = data.get('lines') or []
    if not lines:
        return JsonResponse({'error': 'At least one return line is required.'}, status=400)

    from order.models import PurchaseOrder
    from stock.models import StockItem

    try:
        PurchaseOrder.objects.get(pk=po_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({'error': 'Purchase order not found.'}, status=404)

    validated = []
    for raw in lines:
        try:
            stock = StockItem.objects.get(pk=int(raw.get('stock_item_id')))
            qty = Decimal(str(raw.get('quantity')))
        except (StockItem.DoesNotExist, ValueError, TypeError, InvalidOperation):
            return JsonResponse({'error': 'Invalid stock item or quantity.'}, status=400)

        if qty <= 0 or qty > stock.quantity:
            return JsonResponse({'error': f'Return quantity for stock #{stock.pk} must be greater than zero and no more than {stock.quantity}.'}, status=400)

        stock_po = _stock_po(stock)
        if not stock_po or stock_po.pk != po_id:
            return JsonResponse({'error': f'Stock #{stock.pk} did not originate from PO #{po_id}.'}, status=400)

        committed = sum(
            (x.quantity for x in SupplierReturnLine.objects.filter(
                stock_item_id=stock.pk,
                supplier_return__status__in=['DRAFT', 'READY'],
            )),
            Decimal('0'),
        )
        if committed + qty > stock.quantity:
            return JsonResponse({'error': f'Stock #{stock.pk} does not have enough uncommitted quantity for this return.'}, status=400)

        reason = raw.get('reason')
        resolution = raw.get('requested_resolution')
        if reason not in SupplierReturnLine.Reason.values or resolution not in SupplierReturnLine.Resolution.values:
            return JsonResponse({'error': 'A valid reason and requested resolution are required.'}, status=400)
        validated.append((stock, qty, reason, resolution, raw.get('notes', '')))

    obj = SupplierReturn.objects.create(
        purchase_order_id=po_id,
        supplier_rma=data.get('supplier_rma', ''),
        holding_location_id=data.get('holding_location_id') or None,
        redmine_issue=data.get('redmine_issue', ''),
        notes=data.get('notes', ''),
        created_by=request.user if request.user.is_authenticated else None,
    )

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

    try:
        obj = SupplierReturn.objects.prefetch_related('lines').get(pk=pk)
    except SupplierReturn.DoesNotExist:
        return JsonResponse({'error': 'Supplier Return not found.'}, status=404)

    if request.method == 'GET':
        return JsonResponse(_serialize(obj))

    data = _json_body(request)
    new_status = data.get('status')
    if new_status:
        allowed = {'DRAFT': {'READY', 'CANCELLED'}, 'READY': {'CANCELLED'}, 'CANCELLED': set()}
        if new_status not in allowed.get(obj.status, set()):
            return JsonResponse({'error': f'Cannot change {obj.status} to {new_status}.'}, status=400)
        obj.status = new_status
        obj.save(update_fields=['status', 'updated_at'])
        SupplierReturnEvent.objects.create(
            supplier_return=obj,
            event_type=f'STATUS_{new_status}',
            user=request.user if request.user.is_authenticated else None,
        )
    return JsonResponse(_serialize(obj))


class SupplierReturnPlugin(UrlsMixin, AppMixin, SettingsMixin, UserInterfaceMixin, InvenTreePlugin):
    NAME = 'SupplierReturn'
    SLUG = 'supplier-return'
    TITLE = 'Supplier Return'
    DESCRIPTION = 'Manage supplier returns, RMAs, replacements, credits, refunds and rework with purchase-order and stock traceability.'
    VERSION = '0.2.2'
    AUTHOR = 'Per Vices Corporation'
    WEBSITE = 'https://github.com/bmalatest-dev/inventree-supplier-return'
    LICENSE = 'MIT'

    def setup_urls(self):
        """Register plugin-owned API routes with InvenTree's UrlsMixin."""
        return [
            path('context/<str:model>/<int:pk>/', context_view, name='context'),
            path('returns/', returns_view, name='returns'),
            path('returns/<int:pk>/', return_detail_view, name='return-detail'),
        ]

    SETTINGS = {
        'DEFAULT_HOLDING_LOCATION': {'name': _('Default return holding location'), 'description': _('Optional default; the user can override it for each return.'), 'model': 'stock.stocklocation', 'required': False},
        'DEFAULT_EXTERNAL_LOCATION': {'name': _('Default supplier / external location'), 'description': _('Reserved for the shipping workflow in a later version.'), 'model': 'stock.stocklocation', 'required': False},
        'DEFAULT_RECEIVING_LOCATION': {'name': _('Default return receiving location'), 'description': _('Reserved for the receiving workflow in a later version.'), 'model': 'stock.stocklocation', 'required': False},
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
            'source': self.plugin_static_file('supplier_return.js:renderSupplierReturnPanel'),
            'icon': 'ti:truck-return:outline',
            'context': {
                'target_model': target_model,
                'target_id': target_id,
                'plugin_version': self.VERSION,
                'plugin_base': f'/plugin/{self.SLUG}',
            },
        }]
