# InvenTree Supplier Return / RMA

Initial testable V1 (`0.1.0`) for supplier returns against already-received Purchase Orders.

## V0.1 scope

- One Supplier Return belongs to exactly one Purchase Order.
- Multiple return lines are allowed, but all must originate from that PO.
- Create from a Purchase Order or Stock Item UI panel.
- Original PO receipt is never reversed.
- Creating a return line moves the selected quantity to a user-selected **holding location** using InvenTree's native stock move logic.
- Partial bulk returns are split by InvenTree into a dedicated Stock Item.
- Shipping moves returned stock to a user-selected **external / supplier location** and records carrier / tracking information.
- Replacement / reworked material is received against the Supplier Return, not the completed PO.
- Reworked material preserves the original Stock Item identity.
- Replacement material creates a new Stock Item linked by the Supplier Return receipt record.
- Replacement/reworked stock retains the failed / inspection status until normal inspection changes it.
- Credit, refund and other non-stock resolutions can be recorded separately.
- Partial and mixed resolutions are supported (e.g. 6 replaced + 4 credited).
- A return closes automatically when every line quantity has been fully resolved.
- Failed replacement/reworked material should be handled by creating a new Supplier Return (e.g. SR-0002) against the same original PO.
- Optional Redmine issue field is included.
- Optional default holding / external / receiving locations are exposed as plugin settings. V0.1 still prompts the user; defaults are groundwork for the next UI pass.

## Important V0.1 limitation

The backend workflow is the main target of this first test. The PO / Stock Item panel is deliberately minimal and uses browser prompts so the business logic can be exercised before investing in the final Mantine UI. It does not yet expose every action (ship, receive, credit/refund) as buttons; those endpoints can be tested through the InvenTree-authenticated browser/API and will be wired into the polished UI after the workflow is validated.

Attachments are not included in 0.1.0. Use the Redmine issue field for supporting documents during initial testing.

## Repository

Suggested repository:

`bmalatest-dev/inventree-supplier-return`

## Install in the test instance

From the InvenTree container, install from GitHub after pushing this repository:

```bash
pip install --upgrade --force-reinstall git+https://github.com/bmalatest-dev/inventree-supplier-return
```

Then restart InvenTree. Ensure **Check Plugins on Startup** and plugin UI support are enabled. Enable **Supplier Return / RMA** in the Admin Center.

Because this plugin uses `AppMixin` and custom Django models, the plugin must be enabled and InvenTree restarted so its migrations can be applied. Test only against the local/test database first.

## First test

1. Pick a completed PO with received stock.
2. Open the PO and confirm a **Supplier Returns** panel appears.
3. Alternatively open a Stock Item received from that PO and confirm the same panel appears.
4. From the Stock Item, create a return for a partial quantity and select a holding location.
5. Confirm InvenTree splits/moves the returned quantity while the non-returned quantity stays where it was.
6. Confirm the original PO received quantity is unchanged.
7. Use the API endpoints below to ship, receive or resolve the return.

## API endpoints

All endpoints are below `/plugin/supplier-return/` and require an authenticated InvenTree user.

- `GET/POST api/returns/`
- `GET api/returns/<sr_id>/`
- `POST api/returns/<sr_id>/lines/`
- `POST api/returns/<sr_id>/ready/`
- `POST api/returns/<sr_id>/ship/`
- `POST api/returns/<sr_id>/lines/<line_id>/receive/`
- `POST api/returns/<sr_id>/lines/<line_id>/resolve/`

### Ship example

```json
{
  "external_location": 42,
  "carrier": "FedEx",
  "tracking_number": "123456789"
}
```

### Receive reworked original

```json
{
  "receipt_type": "REWORKED",
  "quantity": 1,
  "receiving_location": 12,
  "notes": "Returned from supplier; requires VI again"
}
```

### Receive replacement

```json
{
  "receipt_type": "REPLACEMENT",
  "quantity": 1,
  "receiving_location": 12,
  "serial": "NEW-SERIAL-001",
  "batch": "RMA-REPLACEMENT",
  "notes": "Replacement received; requires VI"
}
```

### Record credit

```json
{
  "resolution_type": "CREDIT",
  "quantity": 3,
  "amount": "210.00",
  "reference": "CM-12345"
}
```

## Recommended V0.1 validation cases

- Full quantity return.
- Partial bulk quantity return.
- Serialized / traceable stock return.
- Multiple lines from the same PO.
- Attempt to add stock from another PO (must reject).
- Ship to external location.
- Receive same serialized item after rework.
- Receive a new serial as replacement.
- Partial replacement.
- Mixed replacement + credit.
- Confirm original PO received quantities never change.
- Confirm returned/replacement material remains subject to the normal inspection/status process.
