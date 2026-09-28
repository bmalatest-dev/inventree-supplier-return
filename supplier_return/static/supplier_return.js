/* V0.1.1 intentionally provides a minimal, dependency-free UI smoke test. */

export function renderSupplierReturnPanel(target, data) {
  const ctx = (data && data.context) ? data.context : (data || {});
  const model = ctx.target_model || 'record';
  const id = ctx.target_id ?? '';
  const version = ctx.plugin_version || '0.1.1';

  // Older/current InvenTree panel loaders pass an HTMLElement as the first arg.
  if (target && typeof target.innerHTML !== 'undefined') {
    target.innerHTML = `
      <div style="padding: 12px;">
        <h3>Supplier Returns</h3>
        <p>Supplier Return plugin V${version} loaded successfully.</p>
        <p><strong>Context:</strong> ${model} #${id}</p>
        <p>This is the V0.1.1 UI registration milestone. Stock-changing actions are intentionally disabled until this panel is confirmed on the test instance.</p>
      </div>`;
    return;
  }

  // If the 1.6-dev renderer calls this as a component factory, return a basic string.
  return `Supplier Return plugin V${version} loaded successfully for ${model} #${id}`;
}
