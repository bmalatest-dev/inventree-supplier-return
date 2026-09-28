# InvenTree Supplier Return — V0.3.0

Supplier-return / purchasing-RMA workflow for InvenTree.

## V0.3.0 milestone

- Saved DRAFT Supplier Returns are fully editable.
- Create and Edit are distinct actions; editing updates the existing SR.
- Human-readable quantities (e.g. `300`, not `3E+2`).
- `Mark Ready to Return` performs real InvenTree stock segregation:
  - full quantity: moves the selected stock item to the chosen holding location;
  - partial quantity: uses InvenTree's native stock split operation and places the split child in the holding location.
- The Ready transition is wrapped in a database transaction and locks the relevant SR / stock rows.
- Each line records the original stock item, original location, and the stock item physically segregated for return.
- Once READY, stock identity and returned quantity are locked, while Supplier RMA, Redmine issue, notes, and Requested Resolution remain editable.
- Adds the data model for future quantity-level Actual Resolution records (e.g. 300 returned -> 200 replacement + 100 credit). Actual-resolution receiving/accounting UI is intentionally not enabled yet.

## Safety / test note

V0.3.0 is the first version which intentionally changes InvenTree inventory. Test on a non-production InvenTree instance first. The `Mark Ready to Return` confirmation explicitly identifies the quantities which will be moved.
