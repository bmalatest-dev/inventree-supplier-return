# InvenTree Supplier Return

Supplier return / purchasing RMA workflow for InvenTree.

## V0.4.0

- Editable Supplier Return drafts
- Ready-to-Return stock segregation with native InvenTree split / move tracking
- Mark Shipped workflow
- User-selected external / supplier stock location
- Shipment date, carrier, tracking number and shipment notes
- Return stock remains active at the external location while awaiting resolution
- Clickable original and return stock-item links in the Supplier Return panel
- Requested Resolution remains editable after shipment
- Quantity-level Actual Resolution model retained for the next receiving / credit workflow

Stock movement is performed using InvenTree stock operations and Supplier Return state changes are wrapped in database transactions.
