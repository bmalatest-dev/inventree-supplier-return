# InvenTree Supplier Return

V0.1.1 is a deliberately small compatibility milestone for the Per Vices InvenTree 1.6.0-dev test environment.

## Goal of this build

Confirm all of the following before adding database models and stock-changing operations:

1. InvenTree loads the plugin normally and displays its metadata.
2. Plugin version displays as `0.1.1`.
3. Description and author are visible in Plugin Management.
4. A **Supplier Returns** panel appears on a Purchase Order.
5. A **Supplier Returns** panel appears on a Stock Item.
6. The panel identifies the target model / ID and reports that V0.1.1 loaded.

## Planned workflow after this milestone

Purchase Order -> Supplier Return -> Holding Location -> Ship to Supplier -> Receive / Inspect -> Resolve

The full workflow will support multiple lines from one PO, partial returns, RMA/rework, replacement stock, credits/refunds, user-selected locations, Redmine issue reference, and chained SR-0001 / SR-0002 traceability.

## Upgrade test

Update the existing GitHub repository to this version, then run the same plugin update method used for the other Per Vices plugins. Restart the InvenTree application container after the update if required by the local Docker setup.

Do not run production stock movements with this build. V0.1.1 is a registration and UI smoke test only.
