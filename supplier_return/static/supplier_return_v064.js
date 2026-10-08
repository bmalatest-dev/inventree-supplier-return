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
  if (!target || typeof target.innerHTML === 'undefined') return `Supplier Return V${ctx.plugin_version||'0.6.4'}`;
  target.innerHTML='<div style="padding:12px">Loading Supplier Returns…</div>';
  try {
    const state=await api(`${base}/context/${ctx.target_model}/${ctx.target_id}/`);
    let locations=[]; try { const l=await api('/api/stock/location/?limit=500'); locations=l.results||l; } catch(e) {}
    let activeEdit=null;

    const render=()=>{
      const cards=(state.returns||[]).map(r=>{
        const stockLink=(id,text)=>`<a href="/web/stock/item/${id}" title="Open Stock Item #${id}">${esc(text)}</a>`;
        const lines=r.lines.map(x=>{const st=(state.eligible_stock||[]).find(z=>Number(z.id)===Number(x.stock_item_id));const part=st?.part||'';return `<div style="margin:3px 0"><b>${esc(part)}</b>${part?' — ':''}${stockLink(x.stock_item_id,`Stock #${x.stock_item_id}`)}${x.return_stock_item_id&&x.return_stock_item_id!==x.stock_item_id?` → ${stockLink(x.return_stock_item_id,`Return Stock #${x.return_stock_item_id}`)}`:''}: <b>${esc(x.quantity)}</b> — ${esc(label(reasons,x.reason))} / Requested: ${esc(label(resolutions,x.requested_resolution))}</div>`;}).join('');
        let buttons='';
        if(r.status==='DRAFT') buttons=`<button class="sr-edit" data-id="${r.id}">Edit Draft</button> <button class="sr-ready" data-id="${r.id}">Mark Ready to Ship</button> <button class="sr-cancel-return" data-id="${r.id}">Cancel SR</button>`;
        else if(r.status==='READY') buttons=`<button class="sr-admin" data-id="${r.id}">Edit RMA / Requested Resolution</button> <button class="sr-ship" data-id="${r.id}">Mark Shipped</button> <button class="sr-cancel-return" data-id="${r.id}">Cancel SR</button>`;
        else if(['SHIPPED','RESOLUTION'].includes(r.status)) { const physicalPending=r.lines.some(x=>(x.actual_resolutions||[]).some(y=>['REPLACEMENT','REWORK'].includes(y.resolution)&&Number(y.received_quantity||0)<Number(y.quantity||0))); const canClose=r.status==='RESOLUTION' && r.lines.every(x=>(x.actual_resolutions||[]).reduce((a,y)=>a+Number(y.quantity||0),0)===Number(x.quantity||0) && (x.actual_resolutions||[]).every(y=>!['REPLACEMENT','REWORK'].includes(y.resolution)||Number(y.received_quantity||0)===Number(y.quantity||0))); buttons=`<button class="sr-admin" data-id="${r.id}">Edit RMA / Requested Resolution</button> <button class="sr-resolve" data-id="${r.id}">Record Actual Resolution</button>${physicalPending?` <button class="sr-receive-items" data-id="${r.id}">Receive Items</button>`:''}${canClose?` <button class="sr-close" data-id="${r.id}">Close SR</button>`:''}`; }
        const shipment=['SHIPPED','RESOLUTION','CLOSED'].includes(r.status)?`<div style="margin-top:5px"><b>Shipment:</b> ${r.shipment_date?esc(r.shipment_date):'date not recorded'}${r.carrier?` — ${esc(r.carrier)}`:''}${r.tracking_number?` — Tracking: ${esc(r.tracking_number)}`:''}</div>`:'';
        const total=r.lines.reduce((a,x)=>a+Number(x.quantity||0),0), resolved=r.lines.reduce((a,x)=>a+(x.actual_resolutions||[]).reduce((b,y)=>b+Number(y.quantity||0),0),0);
        const progress=['SHIPPED','RESOLUTION','CLOSED'].includes(r.status)?`<div style="margin-top:5px"><b>Resolution:</b> ${resolved} / ${total} resolved — ${Math.max(0,total-resolved)} outstanding</div>`:'';
        const status=r.status==='SHIPPED'?'AWAITING RESOLUTION':r.status==='RESOLUTION'?'RESOLUTION IN PROGRESS':r.status;
        const statusColor=['CLOSED'].includes(r.status)?'#2e7d32':['CANCELLED'].includes(r.status)?'#c62828':'#d6a400'; return `<div style="border:2px solid ${statusColor};border-radius:4px;padding:10px;margin:8px 0"><b>${esc(r.reference)}</b> — <b>${esc(status)}</b>${r.supplier_rma?` — Supplier RMA: ${esc(r.supplier_rma)}`:''}<br>${lines}${shipment}${progress}<div style="margin-top:8px">${buttons}</div></div>`;
      }).join('') || '<p>No Supplier Returns have been created for this PO.</p>';
      target.innerHTML=`<div style="padding:12px"><h3>Supplier Returns</h3><p><b>Purchase Order:</b> #${state.purchase_order_id}</p><div>${cards}</div><hr><button id="sr-all">View All Supplier Returns (Open & Closed)</button> <button id="sr-create">+ Create Supplier Return</button><div id="sr-editor" style="margin-top:12px"></div></div>`;
      wire();
    };

    const stockRows=(r)=> (state.eligible_stock||[]).map(s=>{
      const ln=r?.lines?.find(x=>Number(x.stock_item_id)===Number(s.id));
      const checked=!!ln || (!r && Number(state.preselected_stock_item_id)===Number(s.id));
      return `<label style="display:block;padding:7px;border-bottom:1px solid #ddd"><input type="checkbox" class="sr-stock" value="${s.id}" ${checked?'checked':''}> <b>#${s.id}</b> ${esc(s.part)} — available ${esc(s.quantity)} ${s.batch?`— batch ${esc(s.batch)}`:''} — status ${esc(s.status||'Unknown')} ${s.location?`— ${esc(s.location)}`:''}<span class="sr-line-fields" style="display:${checked?'inline':'none'};margin-left:22px"><br>Qty <input class="sr-qty" type="number" min="0" step="any" value="${esc(ln?.quantity || (checked?s.quantity:''))}" style="width:90px"> Reason <select class="sr-reason">${opts(reasons,ln?.reason||'DEFECTIVE')}</select> Requested Resolution <select class="sr-resolution">${opts(resolutions,ln?.requested_resolution||'REPLACEMENT')}</select><br><span style="margin-left:22px">Line Notes <input class="sr-line-notes" value="${esc(ln?.notes||'')}" style="width:55%"></span></span></label>`;
    }).join('');

    const showDraft=(r=null)=>{
      activeEdit=r;
      const e=target.querySelector('#sr-editor');
      e.innerHTML=`<h4>${r?`Edit ${esc(r.reference)}`:'New Supplier Return'}</h4><p style="color:#555">Draft only — saving does not move stock.</p><label>Supplier RMA # <span style="color:#c62828;font-weight:bold">*</span> <input id="sr-rma" value="${esc(r?.supplier_rma||'')}"><span id="sr-rma-error" style="display:none;color:#c62828;margin-left:6px;font-weight:600"></span></label> <label>Redmine Issue <span style="color:#c62828;font-weight:bold">*</span> <input id="sr-redmine" value="${esc(r?.redmine_issue||'')}" placeholder="#12345 or URL"><span id="sr-redmine-error" style="display:none;color:#c62828;margin-left:6px;font-weight:600"></span></label><br><br><label>Holding Location <span style="color:#c62828;font-weight:bold">*</span> <input id="sr-location-search" list="sr-location-list" value="${esc((locations.find(l=>Number(l.pk||l.id)===Number(r?.holding_location_id))?.pathstring||locations.find(l=>Number(l.pk||l.id)===Number(r?.holding_location_id))?.name)||'')}" placeholder="Type to search locations…"><datalist id="sr-location-list">${locations.map(l=>`<option data-id="${l.pk||l.id}" value="${esc(l.pathstring||l.name)}"></option>`).join('')}</datalist><span id="sr-location-error" style="display:none;color:#c62828;margin-left:6px;font-weight:600"></span></label><br><br><b>Stock to return</b> <button type="button" id="sr-select-all">Select All</button> <button type="button" id="sr-clear-all">Clear All</button><div style="max-height:320px;overflow:auto;border:1px solid #ddd">${stockRows(r)||'<p style="padding:8px">No stock items linked to this PO were found.</p>'}</div><br><label>Notes<br><textarea id="sr-notes" rows="3" style="width:100%">${esc(r?.notes||'')}</textarea></label><br><button id="sr-save">${r?'Save Changes':'Save Draft'}</button> <button id="sr-cancel">Cancel</button> <span id="sr-msg"></span>`;
      e.querySelectorAll('.sr-stock').forEach(c=>{ c.onchange=()=>{const f=c.closest('label').querySelector('.sr-line-fields');f.style.display=c.checked?'inline':'none';if(c.checked&&!f.querySelector('.sr-qty').value){const st=state.eligible_stock.find(x=>String(x.id)===c.value);f.querySelector('.sr-qty').value=st?.quantity||'';}}; });
      const setAll=(checked)=>e.querySelectorAll('.sr-stock').forEach(c=>{c.checked=checked;c.dispatchEvent(new Event('change'));});
      e.querySelector('#sr-select-all').onclick=()=>setAll(true); e.querySelector('#sr-clear-all').onclick=()=>setAll(false);
      e.querySelector('#sr-cancel').onclick=()=>{e.innerHTML='';activeEdit=null;};
      e.querySelector('#sr-save').onclick=async()=>{
        const msg=e.querySelector('#sr-msg'); msg.textContent='Saving…';
        const lines=[...e.querySelectorAll('.sr-stock:checked')].map(c=>{const f=c.closest('label');return {stock_item_id:Number(c.value),quantity:f.querySelector('.sr-qty').value,reason:f.querySelector('.sr-reason').value,requested_resolution:f.querySelector('.sr-resolution').value,notes:f.querySelector('.sr-line-notes').value};});
        const missingOtherNotes=lines.find(x=>(x.reason==='OTHER'||x.requested_resolution==='OTHER')&&!String(x.notes||'').trim());
        if(missingOtherNotes){msg.textContent='Line Notes are required when Reason or Requested Resolution is Other.';return;}
        const clearRequired=(id)=>{const input=e.querySelector(id),err=e.querySelector(`${id}-error`);input.style.border='';input.style.background='';if(err){err.style.display='none';err.textContent='';}}; const invalid=(id,text)=>{const input=e.querySelector(id),err=e.querySelector(`${id}-error`);input.style.border='2px solid #c62828';input.style.background='#fff5f5';if(err){err.textContent=text;err.style.display='inline';}}; ['#sr-rma','#sr-redmine','#sr-location-search'].forEach(clearRequired); const locText=e.querySelector('#sr-location-search').value.trim(); const loc=locations.find(l=>(l.pathstring||l.name)===locText); const rma=e.querySelector('#sr-rma').value.trim(), redmine=e.querySelector('#sr-redmine').value.trim(); let requiredError=false; if(!rma){invalid('#sr-rma','Required');requiredError=true;} if(!redmine){invalid('#sr-redmine','Required');requiredError=true;} if(!loc){invalid('#sr-location-search',locText?'Select a valid location':'Required');requiredError=true;} if(requiredError){msg.textContent='Please complete the required fields highlighted in red.';msg.style.color='#c62828';msg.style.fontWeight='600';return;} msg.style.color='';msg.style.fontWeight=''; const payload={purchase_order_id:state.purchase_order_id,supplier_rma:rma,redmine_issue:redmine,holding_location_id:Number(loc.pk||loc.id),notes:e.querySelector('#sr-notes').value,lines};
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
      if(!confirm(`Mark ${r.reference} Ready to Ship?\n\nThis WILL change inventory. The following quantities will be split if necessary and moved to the selected holding location:\n\n${summary}\n\nThis stock/quantity selection will then be locked.`)) return;
      try { await api(`${base}/returns/${r.id}/`,{method:'PATCH',body:JSON.stringify({action:'mark_ready'})}); location.reload(); }
      catch(ex){alert(`Could not mark Ready to Ship: ${ex.message}`);}
    };

    const showShip=(r)=>{
      const e=target.querySelector('#sr-editor');
      const today=new Date().toISOString().slice(0,10);
      const currentLoc=locations.find(l=>Number(l.pk||l.id)===Number(r.external_location_id));
      e.innerHTML=`<h4>Ship ${esc(r.reference)}</h4><p>This will move the return stock to the selected external supplier location, mark the shipped stock as <b>Returned / unavailable</b>, and change the Supplier Return to <b>Awaiting Resolution</b>.</p><label>Shipment Date <input id="sr-ship-date" type="date" value="${esc(r.shipment_date||today)}"></label><br><br><label>External / Supplier Location <span style="color:#c62828;font-weight:bold">*</span> <input id="sr-external-location" list="sr-external-location-list" value="${esc(currentLoc?.pathstring||currentLoc?.name||'')}" placeholder="Type to search locations…"><datalist id="sr-external-location-list">${locations.map(l=>`<option value="${esc(l.pathstring||l.name)}"></option>`).join('')}</datalist><span id="sr-external-location-error" style="display:none;color:#c62828;margin-left:6px;font-weight:600"></span></label><br><br><label>Carrier <input id="sr-carrier" value="${esc(r.carrier||'')}" placeholder="FedEx, UPS, DHL…"></label> <label>Tracking # <input id="sr-tracking" value="${esc(r.tracking_number||'')}"></label><br><br><label>Shipment Notes<br><textarea id="sr-ship-notes" rows="3" style="width:100%">${esc(r.shipment_notes||'')}</textarea></label><br><button id="sr-ship-confirm">Mark Shipped</button> <button id="sr-ship-cancel">Cancel</button> <span id="sr-msg"></span>`;
      e.querySelector('#sr-ship-cancel').onclick=()=>e.innerHTML='';
      e.querySelector('#sr-ship-confirm').onclick=async()=>{
        const msg=e.querySelector('#sr-msg'), input=e.querySelector('#sr-external-location'), err=e.querySelector('#sr-external-location-error');
        input.style.border=''; input.style.background=''; err.style.display='none';
        const externalText=input.value.trim(); const loc=locations.find(l=>(l.pathstring||l.name)===externalText);
        if(!loc){input.style.border='2px solid #c62828';input.style.background='#fff5f5';err.textContent=externalText?'Select a valid location':'Required';err.style.display='inline';msg.textContent='Select a valid external / supplier location.';msg.style.color='#c62828';return;}
        const stockSummary=r.lines.map(x=>`${x.quantity} from Return Stock #${x.return_stock_item_id||x.stock_item_id}`).join('\n');
        if(!confirm(`Mark ${r.reference} Shipped?\n\nThis WILL move inventory to:\n${loc.pathstring||loc.name}\n\n${stockSummary}\n\nThe shipped return stock will be marked Returned / unavailable and the SR will move to Awaiting Resolution.`)) return;
        msg.style.color='';msg.textContent='Moving stock…';
        try{
          await api(`${base}/returns/${r.id}/`,{method:'PATCH',body:JSON.stringify({action:'mark_shipped',shipment_date:e.querySelector('#sr-ship-date').value,external_location_id:Number(loc.pk||loc.id),carrier:e.querySelector('#sr-carrier').value,tracking_number:e.querySelector('#sr-tracking').value,shipment_notes:e.querySelector('#sr-ship-notes').value})});
          location.reload();
        }catch(ex){msg.textContent=ex.message;}
      };
    };

    const showResolution=(r)=>{
      const e=target.querySelector('#sr-editor');
      const today=new Date().toISOString().slice(0,10);
      const existing=r.lines.flatMap(x=>(x.actual_resolutions||[]).map(y=>({line:x,...y}))).map(y=>{const reversible=r.status!=='CLOSED'&&!['CREDIT','REFUND'].includes(y.resolution)&&Number(y.received_quantity||0)===0&&!y.replacement_stock_item_id;return `<div style="padding:6px;border-bottom:1px solid #ddd"><b>${esc(label(resolutions,y.resolution))}${y.resolution==='OTHER'?' (see notes)':''}: ${esc(y.quantity)}</b> on Return Stock #${y.line.return_stock_item_id||y.line.stock_item_id}${y.reference?` — Ref: ${esc(y.reference)}`:''}${y.amount?` — Amount: ${esc(y.amount)}`:''}${y.notes?` — Notes: ${esc(y.notes)}`:''}${['REPLACEMENT','REWORK'].includes(y.resolution)?` — Received ${esc(y.received_quantity||0)} / ${esc(y.quantity)}`:''}${reversible?` <button class="sr-res-reverse" data-resolution="${y.id}">Reverse</button>`:''}</div>`}).join('');
      const unresolved=r.lines.map(x=>{const done=(x.actual_resolutions||[]).reduce((a,y)=>a+Number(y.quantity||0),0),remaining=Math.max(0,Number(x.quantity)-done);const st=(state.eligible_stock||[]).find(z=>Number(z.id)===Number(x.stock_item_id));return {line:x,remaining,part:st?.part||''};}).filter(x=>x.remaining>0);
      e.innerHTML=`<h4>Actual Resolution — ${esc(r.reference)}</h4>${existing?`<div style="border:1px solid #ddd;margin-bottom:12px"><b style="display:block;padding:6px">Previously Recorded</b>${existing}</div>`:''}${unresolved.length?`<p>Add only the return lines which have actually been resolved by the supplier. Use <b>+ Add Another Resolution</b> to record multiple resolved lines at once.</p><div id="sr-resolution-rows"></div><button id="sr-res-add" type="button">+ Add Another Resolution</button> <button id="sr-res-save">Record Resolutions</button> `:'<p>All return lines have an actual resolution recorded.</p>'}<button id="sr-res-cancel">Cancel</button> <span id="sr-msg"></span>`;
      const rows=e.querySelector('#sr-resolution-rows');
      const selectedIds=()=>Array.from(e.querySelectorAll('.sr-res-line')).map(x=>Number(x.value)).filter(Boolean);
      const lineOptionText=x=>`${x.part?x.part+' — ':''}Return Stock #${x.line.return_stock_item_id||x.line.stock_item_id} — ${x.remaining} outstanding`;
      const refreshLineOptions=()=>{const selected=selectedIds();e.querySelectorAll('.sr-resolution-entry').forEach(card=>{const sel=card.querySelector('.sr-res-line'),current=Number(sel.value);sel.innerHTML='<option value="">Select return line…</option>'+unresolved.filter(x=>x.line.id===current||!selected.includes(Number(x.line.id))).map(x=>`<option value="${x.line.id}" ${Number(x.line.id)===current?'selected':''}>${esc(lineOptionText(x))}</option>`).join('');});};
      const updateCard=(card)=>{const sel=card.querySelector('.sr-res-line'),info=card.querySelector('.sr-res-info'),qty=card.querySelector('.sr-res-qty'),type=card.querySelector('.sr-res-type'),notesLabel=card.querySelector('.sr-res-notes-label'),notes=card.querySelector('.sr-res-notes');const item=unresolved.find(x=>Number(x.line.id)===Number(sel.value));if(item){info.innerHTML=`Returned: <b>${esc(item.line.quantity)}</b> &nbsp; Outstanding: <b>${esc(item.remaining)}</b>`;qty.max=item.remaining;if(!qty.dataset.touched)qty.value=item.remaining;}else{info.textContent='';qty.value='';qty.max='';}const req=type.value==='OTHER';notes.required=req;notesLabel.firstChild.textContent=req?'Notes (required for Other)':'Notes';};
      const addRow=()=>{const idx=e.querySelectorAll('.sr-resolution-entry').length+1,card=document.createElement('div');card.className='sr-resolution-entry';card.style.cssText='border:1px solid #ccc;border-radius:4px;padding:10px;margin:10px 0';card.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center"><b>Resolution ${idx}</b>${idx>1?'<button type="button" class="sr-res-remove">Remove</button>':''}</div><br><label>Return Line <span style="color:#c62828;font-weight:bold">*</span> <select class="sr-res-line"><option value="">Select return line…</option></select></label><div class="sr-res-info" style="margin:7px 0"></div><label>Actual Resolution <span style="color:#c62828;font-weight:bold">*</span> <select class="sr-res-type">${opts(resolutions,'REPLACEMENT')}</select></label> <label>Qty <span style="color:#c62828;font-weight:bold">*</span> <input class="sr-res-qty" type="number" min="0.000001" step="any" style="width:90px"></label><br><br><label>Resolution Date <span style="color:#c62828;font-weight:bold">*</span> <input class="sr-res-date" type="date" value="${today}"></label> <label>Reference <input class="sr-res-ref" placeholder="Credit memo / supplier ref"></label> <label>Amount <input class="sr-res-amount" type="number" step="0.01" placeholder="for credit/refund"></label><br><br><label class="sr-res-notes-label">Notes<br><textarea class="sr-res-notes" rows="2" style="width:100%"></textarea></label><div class="sr-line-error" style="display:none;color:#c62828;font-weight:600;margin-top:5px"></div>`;rows.appendChild(card);refreshLineOptions();const sel=card.querySelector('.sr-res-line'),type=card.querySelector('.sr-res-type'),qty=card.querySelector('.sr-res-qty');sel.onchange=()=>{updateCard(card);refreshLineOptions();};type.onchange=()=>updateCard(card);qty.oninput=()=>qty.dataset.touched='1';card.querySelector('.sr-res-remove')?.addEventListener('click',()=>{card.remove();Array.from(rows.children).forEach((x,i)=>x.querySelector('b').textContent=`Resolution ${i+1}`);refreshLineOptions();});updateCard(card);};
      if(unresolved.length){addRow();e.querySelector('#sr-res-add').onclick=()=>{if(e.querySelectorAll('.sr-resolution-entry').length<unresolved.length)addRow();};}
      e.querySelector('#sr-res-cancel').onclick=()=>e.innerHTML='';
      const save=e.querySelector('#sr-res-save'); if(save) save.onclick=async()=>{const m=e.querySelector('#sr-msg'),payloads=[];let invalid=false;e.querySelectorAll('.sr-resolution-entry').forEach(card=>{const error=card.querySelector('.sr-line-error'),lineId=Number(card.querySelector('.sr-res-line').value),item=unresolved.find(x=>Number(x.line.id)===lineId),type=card.querySelector('.sr-res-type').value,qty=Number(card.querySelector('.sr-res-qty').value),date=card.querySelector('.sr-res-date').value,notes=card.querySelector('.sr-res-notes').value.trim();error.style.display='none';error.textContent='';if(!lineId){error.textContent='Return Line is required.';}else if(!(qty>0)||!item||qty>item.remaining){error.textContent=`Quantity must be greater than 0 and no more than ${item?.remaining??'the outstanding quantity'}.`;}else if(!date){error.textContent='Resolution Date is required.';}else if(type==='OTHER'&&!notes){error.textContent='Notes are required when Actual Resolution is Other.';}if(error.textContent){error.style.display='block';invalid=true;return;}payloads.push({line_id:lineId,resolution:type,quantity:qty,resolution_date:date,reference:card.querySelector('.sr-res-ref').value,amount:card.querySelector('.sr-res-amount').value,notes});});if(invalid||!payloads.length){m.textContent=invalid?'Correct the items highlighted above.':'Add at least one actual resolution.';m.style.color='#c62828';return;}m.style.color='';m.textContent='Saving resolutions…';try{for(const payload of payloads)await api(`${base}/returns/${r.id}/resolutions/`,{method:'POST',body:JSON.stringify(payload)});m.textContent='Resolutions recorded. Refreshing…';window.location.href=window.location.pathname+window.location.search+(window.location.search?'&':'?')+'_sr='+Date.now();}catch(ex){m.textContent=ex.message;m.style.color='#c62828';}};
      e.querySelectorAll('.sr-res-reverse').forEach(b=>b.onclick=async()=>{if(!confirm('Reverse this actual resolution? This restores the quantity to unresolved.'))return;const m=e.querySelector('#sr-msg');m.textContent='Reversing…';try{await api(`${base}/returns/${r.id}/resolutions/${Number(b.dataset.resolution)}/`,{method:'DELETE'});location.reload();}catch(ex){m.textContent=ex.message;}});
    };

    const showReceiveItems=(r)=>{
      const e=target.querySelector('#sr-editor');
      const pending=r.lines.flatMap(line=>(line.actual_resolutions||[]).filter(res=>['REPLACEMENT','REWORK'].includes(res.resolution)&&Number(res.received_quantity||0)<Number(res.quantity||0)).map(res=>({line,res})));
      if(!pending.length){e.innerHTML=`<h4>Receive Items — ${esc(r.reference)}</h4><p>There are no replacement or repair/rework items awaiting receipt.</p><button id="sr-rec-back">Close</button>`;e.querySelector('#sr-rec-back').onclick=()=>e.innerHTML='';return;}
      e.innerHTML=`<h4>Receive Items — ${esc(r.reference)}</h4><p>Select the physical supplier resolution being received. Resolution details are maintained separately by Purchasing.</p>${pending.map(({line,res})=>`<div style="border:1px solid #ddd;border-radius:4px;padding:10px;margin:8px 0"><b>${esc(label(resolutions,res.resolution))}</b> — Stock #${line.return_stock_item_id||line.stock_item_id}<br>Expected: ${esc(res.quantity)} &nbsp; Received: ${esc(res.received_quantity||0)} &nbsp; Remaining: ${Math.max(0,Number(res.quantity)-Number(res.received_quantity||0))}<br><button class="sr-open-receive" data-resolution="${res.id}" style="margin-top:6px">Receive ${res.resolution==='REWORK'?'Repaired Items':'Replacement'}</button></div>`).join('')}<button id="sr-rec-back">Cancel</button>`;
      e.querySelector('#sr-rec-back').onclick=()=>e.innerHTML='';
      e.querySelectorAll('.sr-open-receive').forEach(b=>b.onclick=()=>showReceive(r,Number(b.dataset.resolution)));
    };

    const showReceive=async(r,resId)=>{
      const res=r.lines.flatMap(x=>x.actual_resolutions||[]).find(x=>Number(x.id)===Number(resId)); if(!res)return;
      const box=target.querySelector('#sr-editor');
      const remaining=Number(res.quantity)-Number(res.received_quantity||0);
      const line=r.lines.find(x=>(x.actual_resolutions||[]).some(y=>Number(y.id)===Number(resId)));
      const returnStockId=line?.return_stock_item_id||line?.stock_item_id;
      let oldBatch='';
      try { const stock=await api(`/api/stock/${returnStockId}/`); oldBatch=stock.batch||''; } catch(e) {}
      let statusOptions=[['10','OK'],['50','Attention needed'],['55','Damaged'],['60','Destroyed'],['65','Rejected'],['70','Lost'],['75','Quarantined'],['85','Returned']]; try { const sd=await api('/api/stock/status/'); const raw=sd.values??sd.results??sd; if(Array.isArray(raw)&&raw.length) statusOptions=raw.map(x=>[String(x.key??x.value??x.pk),x.label??x.name??x.text??String(x.key??x.value??x.pk)]); else if(raw&&typeof raw==='object') { const parsed=Object.entries(raw).map(([k,v])=>[String(v?.key??v?.value??k),v?.label??v?.name??v?.text??String(k)]); if(parsed.length) statusOptions=parsed; } } catch(e) {}
      box.innerHTML=`<hr><h4>Receive ${esc(label(resolutions,res.resolution))}</h4><p><b>Expected:</b> ${esc(res.quantity)} &nbsp; <b>Received:</b> ${esc(res.received_quantity||0)} &nbsp; <b>Remaining:</b> ${remaining}</p><label>Receive Quantity <span style="color:#c62828;font-weight:bold">*</span> <input id="sr-rec-qty" type="number" min="0" step="any" value="${remaining}" style="width:90px"></label> <label>Batch ID <input id="sr-rec-batch" value="${esc(oldBatch)}" style="width:180px"></label> <label>Stock Status <span style="color:#c62828;font-weight:bold">*</span> <select id="sr-rec-status">${statusOptions.map(x=>`<option value="${esc(x[0])}" ${String(x[0])==='50'?'selected':''}>${esc(x[1])}</option>`).join('')}</select></label><br><br><label>Receiving / Inspection Location <span style="color:#c62828;font-weight:bold">*</span> <input id="sr-rec-loc" list="sr-rec-loc-list" placeholder="Type to search locations…"><datalist id="sr-rec-loc-list">${locations.map(l=>`<option value="${esc(l.pathstring||l.name)}"></option>`).join('')}</datalist></label><br><br><label>Receipt Notes <input id="sr-rec-notes" style="width:50%"></label><br><small>Stock Tracking will record the Batch ID change from ${esc(oldBatch||'<blank>')} to the entered Batch ID.</small><br><button id="sr-rec-save">Receive</button> <span id="sr-rec-msg"></span>`;
      box.querySelector('#sr-rec-save').onclick=async()=>{const m=box.querySelector('#sr-rec-msg');const locText=box.querySelector('#sr-rec-loc').value.trim(),loc=locations.find(l=>(l.pathstring||l.name)===locText);if(!loc){m.textContent='Select a valid receiving / inspection location.';m.style.color='#c62828';return;}m.style.color='';m.textContent='Receiving…';try{await api(`${base}/returns/${r.id}/resolutions/${res.id}/receive/`,{method:'POST',body:JSON.stringify({quantity:box.querySelector('#sr-rec-qty').value,location_id:Number(loc.pk||loc.id),batch:box.querySelector('#sr-rec-batch').value,status:Number(box.querySelector('#sr-rec-status').value),notes:box.querySelector('#sr-rec-notes').value})});m.textContent='Received successfully. Refreshing…';window.location.href=window.location.pathname+window.location.search+(window.location.search?'&':'?')+'_sr='+Date.now();}catch(ex){m.textContent=ex.message;}};
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
      target.querySelectorAll('.sr-cancel-return').forEach(b=>b.onclick=async()=>{const r=state.returns.find(x=>Number(x.id)===Number(b.dataset.id));const warning=r.status==='READY'?'This will cancel the SR and move the prepared return stock back to its original location.':'This will cancel the Draft SR. No stock has moved yet.';if(!confirm(`Cancel ${r.reference}?\n\n${warning}`))return;try{await api(`${base}/returns/${r.id}/`,{method:'PATCH',body:JSON.stringify({action:'cancel_return'})});location.reload();}catch(ex){alert(ex.message);}});
      target.querySelectorAll('.sr-ship').forEach(b=>b.onclick=()=>showShip(state.returns.find(r=>Number(r.id)===Number(b.dataset.id))));
      target.querySelectorAll('.sr-close').forEach(b=>b.onclick=async()=>{const r=state.returns.find(x=>Number(x.id)===Number(b.dataset.id));if(!confirm(`Close ${r.reference}? All returned quantities must be fully resolved and all replacement/rework quantities received.`))return;try{await api(`${base}/returns/${r.id}/close/`,{method:'POST',body:'{}'});location.reload();}catch(ex){alert(ex.message);}});
      target.querySelectorAll('.sr-resolve').forEach(b=>b.onclick=()=>showResolution(state.returns.find(r=>Number(r.id)===Number(b.dataset.id))));
      target.querySelectorAll('.sr-receive-items').forEach(b=>b.onclick=()=>showReceiveItems(state.returns.find(r=>Number(r.id)===Number(b.dataset.id))));
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
    const shown=rows.filter(r=>(!status||(status==='__OPEN__'?!['CLOSED','CANCELLED'].includes(r.status):r.status===status))&&(!search||`${r.reference} ${r.supplier_name||''} ${r.supplier_rma||''} PO-${r.purchase_order_id}`.toLowerCase().includes(search.toLowerCase())));
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
          h('option',{value:''},'All'),h('option',{value:'__OPEN__'},'Open only'),h('option',{value:'DRAFT'},'Draft'),h('option',{value:'READY'},'Ready to Ship'),h('option',{value:'SHIPPED'},'Awaiting Resolution'),h('option',{value:'RESOLUTION'},'Resolution in Progress'),h('option',{value:'CLOSED'},'Closed'),h('option',{value:'CANCELLED'},'Cancelled'))),
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
