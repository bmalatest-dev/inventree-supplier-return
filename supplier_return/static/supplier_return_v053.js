function esc(v) { return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function cookie(name) { return document.cookie.split('; ').find(x => x.startsWith(name + '='))?.split('=')[1] || ''; }
async function api(url, opts={}) {
  opts.headers = Object.assign({'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(cookie('csrftoken'))}, opts.headers || {});
  const r = await fetch(url, opts), contentType = r.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) throw new Error(`API request failed (HTTP ${r.status}; expected JSON but received ${contentType || 'unknown content type'})`);
  const d = await r.json(); if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`); return d;
}
const reasons=[['DEFECTIVE','Defective / Failed Inspection'],['INCORRECT','Incorrect Item'],['INCORRECT_QTY','Incorrect Quantity'],['DAMAGED','Damaged'],['NOT_REQUIRED','No Longer Required'],['ORDERED_ERROR','Ordered in Error'],['OTHER','Other']];
const resolutions=[['REPLACEMENT','Replacement'],['CREDIT','Credit'],['REFUND','Refund'],['REWORK','Repair / Rework'],['OTHER','Other']];
const label=(items,val)=>items.find(x=>x[0]===val)?.[1]||val;
const opts=(items,val)=>items.map(x=>`<option value="${x[0]}" ${x[0]===val?'selected':''}>${esc(x[1])}</option>`).join('');

export async function renderSupplierReturnPanel(target, data) {
  const ctx=(data&&data.context)?data.context:(data||{}), base=ctx.plugin_base || '/plugin/supplier-return';
  if (!target || typeof target.innerHTML === 'undefined') return `Supplier Return V${ctx.plugin_version||'0.5.1'}`;
  target.innerHTML='<div style="padding:12px">Loading Supplier Returns…</div>';
  try {
    const state=await api(`${base}/context/${ctx.target_model}/${ctx.target_id}/`);
    let locations=[]; try { const l=await api('/api/stock/location/?limit=500'); locations=l.results||l; } catch(e) {}
    let activeEdit=null;

    const render=()=>{
      const cards=(state.returns||[]).map(r=>{
        const stockLink=(id,text)=>`<a href="/web/stock/item/${id}/" title="Open Stock Item #${id}">${esc(text)}</a>`;
        const lines=r.lines.map(x=>`<div style="margin:3px 0">${stockLink(x.stock_item_id,`Stock #${x.stock_item_id}`)}${x.return_stock_item_id&&x.return_stock_item_id!==x.stock_item_id?` → ${stockLink(x.return_stock_item_id,`Return Stock #${x.return_stock_item_id}`)}`:''}: <b>${esc(x.quantity)}</b> — ${esc(label(reasons,x.reason))} / Requested: ${esc(label(resolutions,x.requested_resolution))}</div>`).join('');
        let buttons='';
        if(r.status==='DRAFT') buttons=`<button class="sr-edit" data-id="${r.id}">Edit Draft</button> <button class="sr-ready" data-id="${r.id}">Mark Ready to Return</button>`;
        else if(r.status==='READY') buttons=`<button class="sr-admin" data-id="${r.id}">Edit RMA / Requested Resolution</button> <button class="sr-ship" data-id="${r.id}">Mark Shipped</button>`;
        else if(['SHIPPED','RESOLUTION'].includes(r.status)) { const canClose=r.status==='RESOLUTION' && r.lines.every(x=>(x.actual_resolutions||[]).reduce((a,y)=>a+Number(y.quantity||0),0)===Number(x.quantity||0) && (x.actual_resolutions||[]).every(y=>!['REPLACEMENT','REWORK'].includes(y.resolution)||Number(y.received_quantity||0)===Number(y.quantity||0))); buttons=`<button class="sr-admin" data-id="${r.id}">Edit RMA / Requested Resolution</button> <button class="sr-resolve" data-id="${r.id}">Record Actual Resolution</button>${canClose?` <button class="sr-close" data-id="${r.id}">Close SR</button>`:''}`; }
        const shipment=['SHIPPED','RESOLUTION','CLOSED'].includes(r.status)?`<div style="margin-top:5px"><b>Shipment:</b> ${r.shipment_date?esc(r.shipment_date):'date not recorded'}${r.carrier?` — ${esc(r.carrier)}`:''}${r.tracking_number?` — Tracking: ${esc(r.tracking_number)}`:''}</div>`:'';
        const total=r.lines.reduce((a,x)=>a+Number(x.quantity||0),0), resolved=r.lines.reduce((a,x)=>a+(x.actual_resolutions||[]).reduce((b,y)=>b+Number(y.quantity||0),0),0);
        const progress=['SHIPPED','RESOLUTION','CLOSED'].includes(r.status)?`<div style="margin-top:5px"><b>Resolution:</b> ${resolved} / ${total} resolved — ${Math.max(0,total-resolved)} outstanding</div>`:'';
        const status=r.status==='SHIPPED'?'AWAITING RESOLUTION':r.status==='RESOLUTION'?'RESOLUTION IN PROGRESS':r.status;
        return `<div style="border:1px solid #ccc;border-radius:4px;padding:10px;margin:8px 0"><b>${esc(r.reference)}</b> — <b>${esc(status)}</b>${r.supplier_rma?` — Supplier RMA: ${esc(r.supplier_rma)}`:''}<br>${lines}${shipment}${progress}<div style="margin-top:8px">${buttons}</div></div>`;
      }).join('') || '<p>No Supplier Returns have been created for this PO.</p>';
      target.innerHTML=`<div style="padding:12px"><h3>Supplier Returns</h3><p><b>Purchase Order:</b> #${state.purchase_order_id}</p><div>${cards}</div><hr><button id="sr-all">All Supplier Returns</button> <button id="sr-create">+ Create Supplier Return</button><div id="sr-editor" style="margin-top:12px"></div></div>`;
      wire();
    };

    const stockRows=(r)=> (state.eligible_stock||[]).map(s=>{
      const ln=r?.lines?.find(x=>Number(x.stock_item_id)===Number(s.id));
      const checked=!!ln || (!r && Number(state.preselected_stock_item_id)===Number(s.id));
      return `<label style="display:block;padding:7px;border-bottom:1px solid #ddd"><input type="checkbox" class="sr-stock" value="${s.id}" ${checked?'checked':''}> <b>#${s.id}</b> ${esc(s.part)} — available ${esc(s.quantity)} ${s.batch?`— batch ${esc(s.batch)}`:''} ${s.location?`— ${esc(s.location)}`:''}<span class="sr-line-fields" style="display:${checked?'inline':'none'};margin-left:22px"><br>Qty <input class="sr-qty" type="number" min="0" step="any" value="${esc(ln?.quantity || (checked?s.quantity:''))}" style="width:90px"> Reason <select class="sr-reason">${opts(reasons,ln?.reason||'DEFECTIVE')}</select> Requested Resolution <select class="sr-resolution">${opts(resolutions,ln?.requested_resolution||'REPLACEMENT')}</select><br><span style="margin-left:22px">Line Notes <input class="sr-line-notes" value="${esc(ln?.notes||'')}" style="width:55%"></span></span></label>`;
    }).join('');

    const showDraft=(r=null)=>{
      activeEdit=r;
      const e=target.querySelector('#sr-editor');
      e.innerHTML=`<h4>${r?`Edit ${esc(r.reference)}`:'New Supplier Return'}</h4><p style="color:#555">Draft only — saving does not move stock.</p><label>Supplier RMA # <input id="sr-rma" value="${esc(r?.supplier_rma||'')}"></label> <label>Redmine Issue <input id="sr-redmine" value="${esc(r?.redmine_issue||'')}" placeholder="#12345 or URL"></label><br><br><label>Holding Location <select id="sr-location"><option value="">Select…</option>${locations.map(l=>`<option value="${l.pk||l.id}" ${Number(r?.holding_location_id)===Number(l.pk||l.id)?'selected':''}>${esc(l.pathstring||l.name)}</option>`).join('')}</select></label><br><br><b>Stock to return</b><div style="max-height:320px;overflow:auto;border:1px solid #ddd">${stockRows(r)||'<p style="padding:8px">No stock items linked to this PO were found.</p>'}</div><br><label>Notes<br><textarea id="sr-notes" rows="3" style="width:100%">${esc(r?.notes||'')}</textarea></label><br><button id="sr-save">${r?'Save Changes':'Save Draft'}</button> <button id="sr-cancel">Cancel</button> <span id="sr-msg"></span>`;
      e.querySelectorAll('.sr-stock').forEach(c=>{ c.onchange=()=>{const f=c.closest('label').querySelector('.sr-line-fields');f.style.display=c.checked?'inline':'none';if(c.checked&&!f.querySelector('.sr-qty').value){const st=state.eligible_stock.find(x=>String(x.id)===c.value);f.querySelector('.sr-qty').value=st?.quantity||'';}}; });
      e.querySelector('#sr-cancel').onclick=()=>{e.innerHTML='';activeEdit=null;};
      e.querySelector('#sr-save').onclick=async()=>{
        const msg=e.querySelector('#sr-msg'); msg.textContent='Saving…';
        const lines=[...e.querySelectorAll('.sr-stock:checked')].map(c=>{const f=c.closest('label');return {stock_item_id:Number(c.value),quantity:f.querySelector('.sr-qty').value,reason:f.querySelector('.sr-reason').value,requested_resolution:f.querySelector('.sr-resolution').value,notes:f.querySelector('.sr-line-notes').value};});
        const payload={purchase_order_id:state.purchase_order_id,supplier_rma:e.querySelector('#sr-rma').value,redmine_issue:e.querySelector('#sr-redmine').value,holding_location_id:e.querySelector('#sr-location').value||null,notes:e.querySelector('#sr-notes').value,lines};
        try {
          let saved;
          if(r) saved=await api(`${base}/returns/${r.id}/`,{method:'PATCH',body:JSON.stringify(Object.assign({action:'save_draft'},payload))});
          else saved=await api(`${base}/returns/`,{method:'POST',body:JSON.stringify(payload)});
          msg.textContent=r?`Saved ${saved.reference}`:`Created ${saved.reference}`; setTimeout(()=>location.reload(),500);
        } catch(ex){msg.textContent=ex.message;}
      };
    };

    const markReady=async(r)=>{
      if(!r.holding_location_id){ showDraft(r); const m=target.querySelector('#sr-msg'); if(m)m.textContent='Select a Holding Location and save the draft before marking it Ready.'; return; }
      const summary=r.lines.map(x=>`${x.quantity} from Stock #${x.stock_item_id}`).join('\n');
      if(!confirm(`Mark ${r.reference} Ready to Return?\n\nThis WILL change inventory. The following quantities will be split if necessary and moved to the selected holding location:\n\n${summary}\n\nThis stock/quantity selection will then be locked.`)) return;
      try { await api(`${base}/returns/${r.id}/`,{method:'PATCH',body:JSON.stringify({action:'mark_ready'})}); location.reload(); }
      catch(ex){alert(`Could not mark Ready to Return: ${ex.message}`);}
    };

    const showShip=(r)=>{
      const e=target.querySelector('#sr-editor');
      const today=new Date().toISOString().slice(0,10);
      e.innerHTML=`<h4>Ship ${esc(r.reference)}</h4><p>This will move the return stock to the selected external supplier location and change the Supplier Return to <b>Awaiting Resolution</b>.</p><label>Shipment Date <input id="sr-ship-date" type="date" value="${esc(r.shipment_date||today)}"></label><br><br><label>External / Supplier Location <select id="sr-external-location"><option value="">Select…</option>${locations.map(l=>`<option value="${l.pk||l.id}" ${Number(r.external_location_id)===Number(l.pk||l.id)?'selected':''}>${esc(l.pathstring||l.name)}</option>`).join('')}</select></label><br><br><label>Carrier <input id="sr-carrier" value="${esc(r.carrier||'')}" placeholder="FedEx, UPS, DHL…"></label> <label>Tracking # <input id="sr-tracking" value="${esc(r.tracking_number||'')}"></label><br><br><label>Shipment Notes<br><textarea id="sr-ship-notes" rows="3" style="width:100%">${esc(r.shipment_notes||'')}</textarea></label><br><button id="sr-ship-confirm">Mark Shipped</button> <button id="sr-ship-cancel">Cancel</button> <span id="sr-msg"></span>`;
      e.querySelector('#sr-ship-cancel').onclick=()=>e.innerHTML='';
      e.querySelector('#sr-ship-confirm').onclick=async()=>{
        const msg=e.querySelector('#sr-msg');
        const external=e.querySelector('#sr-external-location').value;
        if(!external){msg.textContent='Select an external / supplier location.';return;}
        const loc=locations.find(l=>String(l.pk||l.id)===String(external));
        const stockSummary=r.lines.map(x=>`${x.quantity} from Return Stock #${x.return_stock_item_id||x.stock_item_id}`).join('\n');
        if(!confirm(`Mark ${r.reference} Shipped?\n\nThis WILL move inventory to:\n${loc?.pathstring||loc?.name||'the selected external location'}\n\n${stockSummary}\n\nThe return will then be Awaiting Resolution.`)) return;
        msg.textContent='Moving stock…';
        try{
          await api(`${base}/returns/${r.id}/`,{method:'PATCH',body:JSON.stringify({action:'mark_shipped',shipment_date:e.querySelector('#sr-ship-date').value,external_location_id:Number(external),carrier:e.querySelector('#sr-carrier').value,tracking_number:e.querySelector('#sr-tracking').value,shipment_notes:e.querySelector('#sr-ship-notes').value})});
          location.reload();
        }catch(ex){msg.textContent=ex.message;}
      };
    };

    const showResolution=(r)=>{
      const e=target.querySelector('#sr-editor');
      const lineOptions=r.lines.map(x=>{const done=(x.actual_resolutions||[]).reduce((a,y)=>a+Number(y.quantity||0),0);return `<option value="${x.id}">Stock #${x.return_stock_item_id||x.stock_item_id} — returned ${esc(x.quantity)} — unresolved ${Math.max(0,Number(x.quantity)-done)}</option>`}).join('');
      const existing=r.lines.flatMap(x=>(x.actual_resolutions||[]).map(y=>({line:x,...y}))).map(y=>`<div style="padding:6px;border-bottom:1px solid #ddd"><b>${esc(label(resolutions,y.resolution))}: ${esc(y.quantity)}</b> on Return Stock #${y.line.return_stock_item_id||y.line.stock_item_id}${y.reference?` — Ref: ${esc(y.reference)}`:''}${y.amount?` — Amount: ${esc(y.amount)}`:''}${['REPLACEMENT','REWORK'].includes(y.resolution)?` — Received ${esc(y.received_quantity||0)} / ${esc(y.quantity)} <button class="sr-receive" data-resolution="${y.id}" data-return="${r.id}">Receive</button>`:''}</div>`).join('');
      e.innerHTML=`<h4>Actual Resolution — ${esc(r.reference)}</h4>${existing?`<div style="border:1px solid #ddd;margin-bottom:12px">${existing}</div>`:''}<label>Return Line <select id="sr-res-line">${lineOptions}</select></label> <label>Actual Resolution <select id="sr-res-type">${opts(resolutions,'REPLACEMENT')}</select></label> <label>Qty <input id="sr-res-qty" type="number" min="0" step="any" style="width:90px"></label><br><br><label>Resolution Date <input id="sr-res-date" type="date" value="${new Date().toISOString().slice(0,10)}"></label> <label>Reference <input id="sr-res-ref" placeholder="Credit memo / supplier ref"></label> <label>Amount <input id="sr-res-amount" type="number" step="0.01" placeholder="for credit/refund"></label><br><br><label>Notes<br><textarea id="sr-res-notes" rows="2" style="width:100%"></textarea></label><br><button id="sr-res-save">Record Resolution</button> <button id="sr-res-cancel">Cancel</button> <span id="sr-msg"></span><div id="sr-receive-box" style="margin-top:12px"></div>`;
      e.querySelector('#sr-res-cancel').onclick=()=>e.innerHTML='';
      e.querySelector('#sr-res-save').onclick=async()=>{const m=e.querySelector('#sr-msg');m.textContent='Saving…';try{await api(`${base}/returns/${r.id}/resolutions/`,{method:'POST',body:JSON.stringify({line_id:Number(e.querySelector('#sr-res-line').value),resolution:e.querySelector('#sr-res-type').value,quantity:e.querySelector('#sr-res-qty').value,resolution_date:e.querySelector('#sr-res-date').value,reference:e.querySelector('#sr-res-ref').value,amount:e.querySelector('#sr-res-amount').value,notes:e.querySelector('#sr-res-notes').value})});location.reload();}catch(ex){m.textContent=ex.message;}};
      e.querySelectorAll('.sr-receive').forEach(b=>b.onclick=()=>showReceive(r,Number(b.dataset.resolution)));
    };

    const showReceive=(r,resId)=>{
      const res=r.lines.flatMap(x=>x.actual_resolutions||[]).find(x=>Number(x.id)===Number(resId)); if(!res)return;
      const box=target.querySelector('#sr-receive-box')||target.querySelector('#sr-editor');
      const remaining=Number(res.quantity)-Number(res.received_quantity||0);
      box.innerHTML=`<hr><h4>Receive ${esc(label(resolutions,res.resolution))}</h4><p><b>Expected:</b> ${esc(res.quantity)} &nbsp; <b>Received:</b> ${esc(res.received_quantity||0)} &nbsp; <b>Remaining:</b> ${remaining}</p><label>Receive Quantity <input id="sr-rec-qty" type="number" min="0" step="any" value="${remaining}" style="width:90px"></label> <label>Receiving / Inspection Location <select id="sr-rec-loc"><option value="">Select…</option>${locations.map(l=>`<option value="${l.pk||l.id}">${esc(l.pathstring||l.name)}</option>`).join('')}</select></label><br><br><label>Receipt Notes <input id="sr-rec-notes" style="width:50%"></label><br><button id="sr-rec-save">Receive</button> <span id="sr-rec-msg"></span>`;
      box.querySelector('#sr-rec-save').onclick=async()=>{const m=box.querySelector('#sr-rec-msg');const loc=box.querySelector('#sr-rec-loc').value;if(!loc){m.textContent='Select a receiving / inspection location.';return;}m.textContent='Receiving…';try{await api(`${base}/returns/${r.id}/resolutions/${res.id}/receive/`,{method:'POST',body:JSON.stringify({quantity:box.querySelector('#sr-rec-qty').value,location_id:Number(loc),notes:box.querySelector('#sr-rec-notes').value})});location.reload();}catch(ex){m.textContent=ex.message;}};
    };

    const showAdmin=(r)=>{
      const e=target.querySelector('#sr-editor');
      e.innerHTML=`<h4>Edit ${esc(r.reference)}</h4><p>Returned stock and quantities are locked. Supplier details and requested resolution can still change.</p><label>Supplier RMA # <input id="sr-rma" value="${esc(r.supplier_rma||'')}"></label> <label>Redmine Issue <input id="sr-redmine" value="${esc(r.redmine_issue||'')}"></label><br><br>${r.lines.map(x=>`<div>Stock #${x.return_stock_item_id||x.stock_item_id}: ${esc(x.quantity)} — Requested Resolution <select class="sr-admin-res" data-line="${x.id}">${opts(resolutions,x.requested_resolution)}</select></div>`).join('')}<br><label>Notes<br><textarea id="sr-notes" rows="3" style="width:100%">${esc(r.notes||'')}</textarea></label><br><button id="sr-admin-save">Save Changes</button> <button id="sr-admin-cancel">Cancel</button> <span id="sr-msg"></span>`;
      e.querySelector('#sr-admin-cancel').onclick=()=>e.innerHTML='';
      e.querySelector('#sr-admin-save').onclick=async()=>{const msg=e.querySelector('#sr-msg');msg.textContent='Saving…';const rr={};e.querySelectorAll('.sr-admin-res').forEach(s=>rr[s.dataset.line]=s.value);try{await api(`${base}/returns/${r.id}/`,{method:'PATCH',body:JSON.stringify({action:'update_admin',supplier_rma:e.querySelector('#sr-rma').value,redmine_issue:e.querySelector('#sr-redmine').value,notes:e.querySelector('#sr-notes').value,requested_resolutions:rr})});location.reload();}catch(ex){msg.textContent=ex.message;}};
    };

    const wire=()=>{
      target.querySelector('#sr-all').onclick=()=>{window.location.href='/plugin/supplier-return/queue/';};
      target.querySelector('#sr-create').onclick=()=>showDraft(null);
      target.querySelectorAll('.sr-edit').forEach(b=>b.onclick=()=>showDraft(state.returns.find(r=>Number(r.id)===Number(b.dataset.id))));
      target.querySelectorAll('.sr-ready').forEach(b=>b.onclick=()=>markReady(state.returns.find(r=>Number(r.id)===Number(b.dataset.id))));
      target.querySelectorAll('.sr-ship').forEach(b=>b.onclick=()=>showShip(state.returns.find(r=>Number(r.id)===Number(b.dataset.id))));
      target.querySelectorAll('.sr-close').forEach(b=>b.onclick=async()=>{const r=state.returns.find(x=>Number(x.id)===Number(b.dataset.id));if(!confirm(`Close ${r.reference}? All returned quantities must be fully resolved and all replacement/rework quantities received.`))return;try{await api(`${base}/returns/${r.id}/close/`,{method:'POST',body:'{}'});location.reload();}catch(ex){alert(ex.message);}});
      target.querySelectorAll('.sr-resolve').forEach(b=>b.onclick=()=>showResolution(state.returns.find(r=>Number(r.id)===Number(b.dataset.id))));
      target.querySelectorAll('.sr-admin').forEach(b=>b.onclick=()=>showAdmin(state.returns.find(r=>Number(r.id)===Number(b.dataset.id))));
    };
    render();
  } catch(e) { target.innerHTML=`<div style="padding:12px;color:#c00"><b>Supplier Return error:</b> ${esc(e.message)}</div>`; }
}

export function getSupplierReturnQueue(data) {
  const React = window.React;
  if (!React) return 'Supplier Returns';
  const ctx=(data&&data.context)?data.context:(data||{});
  const base=ctx.plugin_base||'/plugin/supplier-return';

  function QueuePage() {
    const [rows,setRows]=React.useState([]);
    const [status,setStatus]=React.useState('');
    const [search,setSearch]=React.useState('');
    const [error,setError]=React.useState('');
    const [loading,setLoading]=React.useState(true);

    React.useEffect(()=>{
      let alive=true;
      api(`${base}/returns/`).then(payload=>{
        if(alive){setRows(payload.results||[]);setLoading(false);}
      }).catch(e=>{if(alive){setError(e.message);setLoading(false);}});
      return ()=>{alive=false;};
    },[]);

    const statusName=s=>s==='SHIPPED'?'Awaiting Resolution':s==='RESOLUTION'?'Resolution in Progress':String(s||'').replaceAll('_',' ');
    const summary=r=>{const returned=r.lines.reduce((a,x)=>a+Number(x.quantity||0),0);const resolved=r.lines.reduce((a,x)=>a+(x.actual_resolutions||[]).reduce((b,y)=>b+Number(y.quantity||0),0),0);const received=r.lines.reduce((a,x)=>a+(x.actual_resolutions||[]).reduce((b,y)=>b+Number(y.received_quantity||0),0),0);return {returned,resolved,received};};
    const shown=rows.filter(r=>(!status||r.status===status)&&(!search||`${r.reference} ${r.supplier_name||''} ${r.supplier_rma||''} PO-${r.purchase_order_id}`.toLowerCase().includes(search.toLowerCase())));
    const h=React.createElement;
    const cell=(v,props={})=>h('td',Object.assign({style:{padding:'8px',borderBottom:'1px solid #ddd',textAlign:'left'}},props),v);
    const head=t=>h('th',{style:{padding:'8px',borderBottom:'1px solid #ddd',textAlign:'left'}},t);
    if(loading) return h('div',{style:{padding:'16px'}},'Loading Supplier Returns…');
    if(error) return h('div',{style:{padding:'16px',color:'#c00'}},`Supplier Return queue error: ${error}`);
    return h('div',{style:{padding:'16px'}},
      h('h2',null,'Supplier Returns'),
      h('p',null,'Operational queue for supplier returns, RMAs and outstanding resolutions.'),
      h('div',{style:{display:'flex',gap:'8px',marginBottom:'12px'}},
        h('label',null,'Status ',h('select',{value:status,onChange:e=>setStatus(e.target.value)},
          h('option',{value:''},'All'),h('option',{value:'DRAFT'},'Draft'),h('option',{value:'READY'},'Ready to Return'),h('option',{value:'SHIPPED'},'Awaiting Resolution'),h('option',{value:'RESOLUTION'},'Resolution in Progress'),h('option',{value:'CLOSED'},'Closed'),h('option',{value:'CANCELLED'},'Cancelled'))),
        h('input',{value:search,onChange:e=>setSearch(e.target.value),placeholder:'Search SR / RMA / PO'})
      ),
      h('div',{style:{overflow:'auto'}},h('table',{style:{width:'100%',borderCollapse:'collapse'}},
        h('thead',null,h('tr',null,...['SR','Supplier','Original PO','Supplier RMA','Status','Returned','Resolved','Outstanding','Received','Created','Shipped',''].map(head))),
        h('tbody',null,...(shown.length?shown.map(r=>{const q=summary(r);const poUrl=`/web/purchasing/purchase-order/${r.purchase_order_id}/supplier-return-panel`;return h('tr',{key:r.id},
          cell(h('b',null,r.reference)),cell(r.supplier_name||'—'),cell(h('a',{href:poUrl},`PO #${r.purchase_order_id}`)),cell(r.supplier_rma||'—'),cell(h('b',null,statusName(r.status))),cell(q.returned),cell(q.resolved),cell(Math.max(0,q.returned-q.resolved)),cell(q.received),cell((r.created_at||'').slice(0,10)),cell(r.shipment_date||'—'),cell(h('a',{href:poUrl},'Open')));}) : [h('tr',{key:'none'},cell('No Supplier Returns found.',{colSpan:12}))]))
      ))
    );
  }
  return React.createElement(QueuePage);
}
