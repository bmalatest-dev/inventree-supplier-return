# InvenTree Supplier Return — v0.2.1

First persisted workflow build for InvenTree 1.6.0-dev / API 538.

## Included

- Supplier Returns panel on Purchase Orders and Stock Items
- Persistent `SupplierReturn`, `SupplierReturnLine`, and `SupplierReturnEvent` models
- Automatic `SR-0001`, `SR-0002`, ... references
- One Supplier Return per originating PO; multiple stock lines from that PO are supported
- Draft creation with supplier RMA, Redmine issue, holding location, notes, quantity, reason, and requested resolution
- Server-side validation that returned stock originates from the selected PO, quantities are positive / available, and quantity is not already committed to another open Supplier Return
- Draft / Ready to Return / Cancelled status model
- No stock movement yet: marking Ready is intentionally only a workflow state in v0.2.1

## Upgrade / install

Update the plugin from GitHub, then run the normal InvenTree plugin/update process so the new Django migration is applied and plugin static files are collected. Restart InvenTree afterwards.

Because v0.2.1 introduces `AppMixin` database models, ensure InvenTree application plugins are enabled in the instance configuration. Test only on a non-production instance first.

## Test

1. Open a PO with stock already received against it.
2. Open **Supplier Returns**.
3. Click **Create Supplier Return**.
4. Select one or more received stock items from that PO.
5. Enter quantity, reason, requested resolution and holding location.
6. Save Draft.
7. Confirm an `SR-####` record appears after reload.
8. Open one of those Stock Items and confirm the same PO Supplier Return history is visible.

v0.2.1 does **not** move stock to the holding location. That is the next milestone after persistence and validation are confirmed.
