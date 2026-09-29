# InvenTree Supplier Return v0.5.7

Supplier-return / RMA workflow for InvenTree.

## v0.5.7

Replacement / rework receipt improvements:

- Adds an editable Batch ID field when physical replacement or reworked stock is received.
- Defaults the Batch ID to the returned stock item's current batch, while allowing the receiver to assign the new Per Vices package ID.
- Adds a Stock Status selector at receipt, defaulting to **Attention needed** so newly received material can remain visibly pending inspection.
- Attempts to load configured InvenTree stock statuses (including custom statuses), with built-in status choices as a fallback.
- Records the old-to-new Batch ID transition in the received stock item's Stock Tracking notes.
- Records the selected stock status in the receipt tracking / Supplier Return event history.
- Each partial receipt can use its own Batch ID and status.

No database migration is required. Navigation remains on the known v0.5.5 implementation.

## v0.5.5

Makes the working server-hosted Supplier Returns queue the sole central queue entry point. The navigation remains pointed at `/plugin/supplier-return/queue/`, and the unused React plugin route is no longer advertised, preventing the stale `/web/plugin/supplier-return/returns` Page Not Found path from competing with the working queue. Supplier display behavior is unchanged. No database migration is required.

## v0.5.4

Fixes the server-hosted Supplier Returns queue rendering error caused by Python `str.format()` interpreting CSS and JavaScript braces as format fields. The queue now inserts only the two intended dynamic HTML fragments using targeted token replacement. No database migration is required.

## v0.5.3
- Adds a central **Supplier Returns** operational queue via an InvenTree plugin UI route and navigation item.
- Adds quantity-level **Actual Resolution** records (Replacement, Credit, Refund, Repair/Rework, Other).
- Supports mixed and partial outcomes, e.g. 300 returned -> 200 replacement + 100 credit.
- Separates supplier resolution from physical receipt.
- Adds PO-like receiving for Replacement and Repair/Rework resolutions with Expected / Received / Remaining quantities.
- Replacement receipts create new stock and do not receive again against the original PO.
- Repair/Rework receipts preserve the returned stock identity where possible.
- Credit / Refund dispositions reduce the externally-held return stock when recorded.
- Adds **Resolution in Progress** and explicit close validation.
- Retains PO and Stock Item contextual panels.

> Database migration `0005_resolution_receipts` is included.


## 0.5.3
- Fix custom Supplier Returns queue route to render as an InvenTree React route.
- Use the documented relative plugin navigation URL.
- No database migration changes from 0.5.0.


## V0.5.3
Adds a dependable server-hosted central Supplier Returns queue at `/plugin/supplier-return/queue/`. Navigation and the All Supplier Returns button now use this queue, avoiding the dynamic React-route mounting issue observed in the tested InvenTree 1.6-dev frontend. No database migration is required.
