function esc(v) { return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function cookie(name) { return document.cookie.split('; ').find(x => x.startsWith(name + '='))?.split('=')[1] || ''; }
async function api(url, opts={}) {
  opts.headers = Object.assign({'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(cookie('csrftoken'))}, opts.headers || {});
  const r = await fetch(url, opts); const d = await r.json(); if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`); return d;
}
const reasons=[['DEFECTIVE','Defective / Failed Inspection'],['INCORRECT','Incorrect Material'],['DAMAGED','Damaged'],['NOT_REQUIRED','No Longer Required'],['ORDERED_ERROR','Ordered in Error'],['OTHER','Other']];
const resolutions=[['REPLACEMENT','Replacement'],['CREDIT','Credit'],['REFUND','Refund'],['REWORK','Repair / Rework'],['OTHER','Other']];

export async function renderSupplierReturnPanel(target, data) {
  const ctx=(data&&data.context)?data.context:(data||{}), base=ctx.plugin_base || '/plugin/supplier-return';
  if (!target || typeof target.innerHTML === 'undefined') return `Supplier Return V${ctx.plugin_version||'0.2.0'}`;
  target.innerHTML='<div style="padding:12px">Loading Supplier Returns…</div>';
  try {
    const state=await api(`${base}/context/${ctx.target_model}/${ctx.target_id}/`);
    let locations=[]; try { const l=await api('/api/stock/location/?limit=500'); locations=l.results||l; } catch(e) {}
    const selected=state.preselected_stock_item_id;
    const rows=(state.eligible_stock||[]).map(s=>`<label style="display:block;padding:6px;border-bottom:1px solid #ddd"><input type="checkbox" class="sr-stock" value="${s.id}" ${selected==s.id?'checked':''}> <b>#${s.id}</b> ${esc(s.part)} — available ${esc(s.quantity)} ${s.serial?`— serial ${esc(s.serial)}`:''} ${s.batch?`— batch ${esc(s.batch)}`:''} ${s.location?`— ${esc(s.location)}`:''}<span class="sr-line-fields" style="display:none;margin-left:22px"><br>Qty <input class="sr-qty" type="number" min="0" step="any" style="width:90px"> Reason <select class="sr-reason">${reasons.map(x=>`<option value="${x[0]}">${x[1]}</option>`).join('')}</select> Resolution <select class="sr-resolution">${resolutions.map(x=>`<option value="${x[0]}">${x[1]}</option>`).join('')}</select></span></label>`).join('');
    const cards=(state.returns||[]).map(r=>`<div style="border:1px solid #ddd;border-radius:4px;padding:10px;margin:8px 0"><b>${esc(r.reference)}</b> — ${esc(r.status)} ${r.supplier_rma?`— Supplier RMA: ${esc(r.supplier_rma)}`:''}<br>${r.lines.map(x=>`Stock #${x.stock_item_id}: ${x.quantity} — ${esc(x.reason)} / ${esc(x.requested_resolution)}`).join('<br>')}</div>`).join('') || '<p>No Supplier Returns have been created for this PO.</p>';
    target.innerHTML=`<div style="padding:12px"><h3>Supplier Returns</h3><p><b>Purchase Order:</b> #${state.purchase_order_id}</p><div>${cards}</div><hr><button id="sr-toggle">Create Supplier Return</button><div id="sr-form" style="display:none;margin-top:12px"><h4>New Supplier Return</h4><label>Supplier RMA # <input id="sr-rma"></label> <label>Redmine Issue <input id="sr-redmine" placeholder="#12345 or URL"></label><br><br><label>Holding Location <select id="sr-location"><option value="">Select…</option>${locations.map(l=>`<option value="${l.pk||l.id}">${esc(l.pathstring||l.name)}</option>`).join('')}</select></label><br><br><b>Stock to return</b><div style="max-height:300px;overflow:auto;border:1px solid #ddd">${rows || '<p style="padding:8px">No stock items linked to this PO were found.</p>'}</div><br><label>Notes<br><textarea id="sr-notes" rows="3" style="width:100%"></textarea></label><br><button id="sr-save">Save Draft</button> <span id="sr-msg"></span></div></div>`;
    target.querySelector('#sr-toggle').onclick=()=>{ const f=target.querySelector('#sr-form'); f.style.display=f.style.display==='none'?'block':'none'; };
    target.querySelectorAll('.sr-stock').forEach(c=>{ const sync=()=>{ const f=c.closest('label').querySelector('.sr-line-fields'); f.style.display=c.checked?'inline':'none'; if(c.checked&&!f.querySelector('.sr-qty').value){ const st=state.eligible_stock.find(x=>String(x.id)===c.value); f.querySelector('.sr-qty').value=st?.quantity||''; }}; c.onchange=sync; sync(); });
    target.querySelector('#sr-save').onclick=async()=>{
      const msg=target.querySelector('#sr-msg'); msg.textContent='Saving…';
      const lines=[...target.querySelectorAll('.sr-stock:checked')].map(c=>{const f=c.closest('label');return {stock_item_id:Number(c.value),quantity:f.querySelector('.sr-qty').value,reason:f.querySelector('.sr-reason').value,requested_resolution:f.querySelector('.sr-resolution').value};});
      try { const r=await api(`${base}/returns/`,{method:'POST',body:JSON.stringify({purchase_order_id:state.purchase_order_id,supplier_rma:target.querySelector('#sr-rma').value,redmine_issue:target.querySelector('#sr-redmine').value,holding_location_id:target.querySelector('#sr-location').value||null,notes:target.querySelector('#sr-notes').value,lines})}); msg.textContent=`Created ${r.reference}`; setTimeout(()=>location.reload(),600); } catch(e){ msg.textContent=e.message; }
    };
  } catch(e) { target.innerHTML=`<div style="padding:12px;color:#c00"><b>Supplier Return error:</b> ${esc(e.message)}</div>`; }
}
