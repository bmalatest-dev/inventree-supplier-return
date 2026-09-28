/* Minimal V0.1 UI. Intentionally dependency-free: React is supplied by InvenTree. */

const h = React.createElement;

function unwrap(ctx) {
  return (ctx && ctx.context) ? ctx.context : (ctx || {});
}

async function apiRequest(ctx, method, url, data) {
  if (ctx && ctx.api) {
    const result = await ctx.api.request({ method, url, data });
    return result.data;
  }
  const response = await fetch(url, {
    method,
    credentials: 'same-origin',
    headers: {'Content-Type': 'application/json'},
    body: data ? JSON.stringify(data) : undefined,
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || 'Request failed');
  return body;
}

export function renderSupplierReturnPanel(ctx) {
  const info = unwrap(ctx);
  const model = info.target_model;
  const id = info.target_id;
  const [rows, setRows] = React.useState([]);
  const [message, setMessage] = React.useState('');

  const base = '/plugin/supplier-return/api/returns/';

  async function refresh() {
    try {
      const query = model === 'purchaseorder' ? `?purchase_order=${id}` : `?stock_item=${id}`;
      setRows(await apiRequest(ctx, 'GET', base + query));
      setMessage('');
    } catch (e) { setMessage(String(e)); }
  }

  React.useEffect(() => { refresh(); }, [model, id]);

  async function createReturn() {
    try {
      let po = model === 'purchaseorder' ? id : prompt('Purchase Order ID for this Stock Item:');
      if (!po) return;
      const holding = prompt('Holding Location ID:');
      if (!holding) return;
      const supplierRma = prompt('Supplier RMA / authorization number (optional):') || '';
      const redmine = prompt('Redmine issue (optional):') || '';
      const resolution = prompt('Requested resolution: REPLACEMENT, REWORK, CREDIT, REFUND, OTHER', 'REPLACEMENT') || 'REPLACEMENT';
      const notes = prompt('Return notes (optional):') || '';

      const payload = {
        purchase_order: Number(po), holding_location: Number(holding), supplier_rma: supplierRma,
        redmine_issue: redmine, requested_resolution: resolution.toUpperCase(), notes
      };

      if (model === 'stockitem') {
        payload.stock_item = Number(id);
        payload.quantity = prompt('Quantity to return:');
        payload.reason = (prompt('Reason: DEFECTIVE, INCORRECT, DAMAGED, NOT_REQUIRED, ORDER_ERROR, OTHER', 'DEFECTIVE') || 'OTHER').toUpperCase();
        const poLine = prompt('PO Line ID (leave blank if InvenTree can determine it uniquely):') || '';
        if (poLine) payload.po_line = Number(poLine);
      }

      const result = await apiRequest(ctx, 'POST', base, payload);
      setMessage(`Created ${result.reference}`);
      await refresh();
    } catch (e) { setMessage(String(e)); }
  }

  const cards = rows.map((r) => h('div', {key: r.pk, style: {padding: '8px 0', borderBottom: '1px solid #ddd'}},
    h('strong', null, r.reference),
    ` — ${r.status} — ${r.supplier_name || ''}`,
    r.supplier_rma ? ` — RMA ${r.supplier_rma}` : ''
  ));

  return h('div', {style: {padding: 8}},
    h('div', {style: {display: 'flex', gap: 8, marginBottom: 8}},
      h('button', {onClick: createReturn}, 'Create Supplier Return'),
      h('button', {onClick: refresh}, 'Refresh')
    ),
    message ? h('div', {style: {marginBottom: 8}}, message) : null,
    rows.length ? cards : h('div', null, 'No Supplier Returns found for this record.')
  );
}
