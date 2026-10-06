# InvenTree Supplier Return v0.6.2

## v0.6.2 workflow release

- Renames the prepared state from **Ready to Return** to **Ready to Ship**.
- Requires Supplier RMA # and Redmine Issue with clear validation messages.
- Adds Select All / Clear All for eligible return stock.
- Makes the Holding Location field searchable by typing.
- Displays Part Name alongside stock items in the SR panel.
- Keeps requested resolution separate from the supplier's actual resolution.
- Adds an explicit **Receive Items** purchaser handoff for Replacement and Repair/Rework resolutions.
- Blocks physical receiving until Purchasing marks the applicable resolution Receive Items.
- Loads configured InvenTree stock statuses at receiving, including custom statuses when exposed by the InvenTree API, with built-in statuses as fallback.
- Improves visual state indication and refreshes the page with a cache-busting URL after successful receipt to avoid stale receiving state.
- Adds database migration `0006_ready_to_receive`.

# v0.5.13

Final workflow polish based on validated v0.5.11 behavior:

- Stock Tracking now records the human-readable selected stock status (for example, `Attention needed`) instead of only the numeric status code (`50`).
- Supplier Returns queue adds an **Open only** filter which excludes Closed and Cancelled returns.
- Restores the top-header **Supplier Returns** link as a native InvenTree plugin UI route at `/web/plugin/supplier-return/returns`.
- The proven server queue at `/plugin/supplier-return/queue/` remains available as a fallback.
- No database migration is required.

# InvenTree Supplier Return v0.5.7

## v0.5.11

Fixes replacement receipt traceability and stock-item links. Replacement receipts now create an explicit native InvenTree Stock Tracking update recording the Supplier Return reference, source return-stock item, old-to-new Batch ID transition, selected stock status, and the user performing the receipt. Stock-item links now use InvenTree's canonical `/web/stock/item/<id>` route without the invalid trailing slash. No database migration is required.


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

### v0.5.13

Fixes the top-level **Supplier Returns** header navigation. The navigation item now uses the absolute server-hosted URL `/plugin/supplier-return/queue/` (including the required leading slash), rather than the React route `plugin/supplier-return/returns`. The unused React queue route advertisement has also been removed so there is a single central queue entry point. No database migration is required.

