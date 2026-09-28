"""InvenTree Supplier Return plugin - V0.1.1 registration / UI milestone."""

from django.utils.translation import gettext_lazy as _
from plugin import InvenTreePlugin
from plugin.mixins import SettingsMixin, UserInterfaceMixin


class SupplierReturnPlugin(SettingsMixin, UserInterfaceMixin, InvenTreePlugin):
    """Supplier Return / RMA workflow for received purchase-order stock."""

    NAME = "SupplierReturn"
    SLUG = "supplier-return"
    TITLE = "Supplier Return"
    DESCRIPTION = (
        "Manage supplier returns, RMAs, replacements, credits, refunds and "
        "rework with purchase-order and stock traceability."
    )
    VERSION = "0.1.1"
    AUTHOR = "Per Vices Corporation"
    WEBSITE = "https://github.com/bmalatest-dev/inventree-supplier-return"
    LICENSE = "MIT"

    SETTINGS = {
        "DEFAULT_HOLDING_LOCATION": {
            "name": _("Default return holding location"),
            "description": _("Optional default; the user can override it for each return."),
            "model": "stock.stocklocation",
            "required": False,
        },
        "DEFAULT_EXTERNAL_LOCATION": {
            "name": _("Default supplier / external location"),
            "description": _("Optional default; the user can override it when shipping."),
            "model": "stock.stocklocation",
            "required": False,
        },
        "DEFAULT_RECEIVING_LOCATION": {
            "name": _("Default return receiving location"),
            "description": _("Optional default; the user can override it when receiving."),
            "model": "stock.stocklocation",
            "required": False,
        },
    }

    def get_ui_panels(self, request, context, **kwargs):
        """Expose a Supplier Returns panel on Purchase Orders and Stock Items."""
        context = context or {}
        target_model = context.get("target_model")
        target_id = context.get("target_id")

        if target_id is None or target_model not in {"purchaseorder", "stockitem"}:
            return []

        return [
            {
                "key": "supplier-return-panel",
                "title": _("Supplier Returns"),
                "description": _("Supplier returns and RMA activity for this record."),
                "source": self.plugin_static_file("supplier_return.js:renderSupplierReturnPanel"),
                "icon": "ti:truck-return:outline",
                "context": {
                    "target_model": target_model,
                    "target_id": target_id,
                    "plugin_version": self.VERSION,
                },
            }
        ]
