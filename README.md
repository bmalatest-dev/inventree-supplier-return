# InvenTree Supplier Return — v0.2.3

## v0.2.3 draft-workflow UI milestone

This release keeps the working v0.2.2 URL/App integration and exposes the persisted draft workflow in the PO / Stock Item panel.

### Changes
- Uses a new static module filename (`supplier_return_v023.js`) so the old V0.1.1 milestone panel cannot be reused from a stale collected/static browser asset.
- Displays existing Supplier Returns for the originating PO.
- Adds **Create Supplier Return** with stock selection, quantity, controlled reason, requested resolution, line notes, holding location, supplier RMA, Redmine issue and header notes.
- Adds **Incorrect Quantity** as a controlled return reason and renames **Incorrect Material** to **Incorrect Item**.
- Saves a persistent Draft (`SR-####`) only. No stock is moved in this release.
- Stock Item context continues to show Supplier Return history for its originating PO.

### Intended test
1. Install/update the plugin and collect plugin static files.
2. Apply migrations and restart InvenTree.
3. Open a completed PO which has received stock.
4. Open **Supplier Returns** and verify the real draft UI appears (not the V0.1.1 milestone text).
5. Click **Create Supplier Return** and select one or more stock items received against that PO.
6. Enter quantity, reason, requested resolution, holding location and optional RMA / Redmine / notes.
7. Click **Save Draft**.
8. Confirm an `SR-####` record appears after reload.
9. Open one of the selected Stock Items and confirm the same PO Supplier Return history is visible.

No stock movement is performed by v0.2.3. `READY` remains a workflow state only.
