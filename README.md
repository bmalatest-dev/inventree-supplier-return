# InvenTree Supplier Return v0.5.0

Supplier-return / RMA workflow for InvenTree.

## v0.5.0
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
