"""InvenTree Supplier Return plugin."""

from django.utils.translation import gettext_lazy as _
from plugin import InvenTreePlugin
from plugin.mixins import AppMixin, SettingsMixin, UrlsMixin, UserInterfaceMixin


class SupplierReturnPlugin(
    SettingsMixin,
    UserInterfaceMixin,
    UrlsMixin,
    AppMixin,
    InvenTreePlugin,
):
    """Supplier Return / RMA workflow for received purchase-order stock."""

    NAME = "SupplierReturn"
    SLUG = "supplier-return"
    TITLE = "Supplier Return / RMA"
    DESCRIPTION = "Track supplier returns from PO receipt through shipment and resolution."
    VERSION = "0.1.0"
    AUTHOR = "Per Vices Corporation"
    WEBSITE = "https://github.com/bmalatest-dev/inventree-supplier-return"
    LICENSE = "MIT"

    SETTINGS = {
        "DEFAULT_HOLDING_LOCATION": {
            "name": _("Default return holding location"),
            "description": _("Optional default. Users can override it for each return."),
            "model": "stock.stocklocation",
            "required": False,
        },
        "DEFAULT_EXTERNAL_LOCATION": {
            "name": _("Default supplier / external location"),
            "description": _("Optional default used when material is shipped to a supplier."),
            "model": "stock.stocklocation",
            "required": False,
        },
        "DEFAULT_RECEIVING_LOCATION": {
            "name": _("Default return receiving location"),
            "description": _("Optional default used when replacement or reworked material returns."),
            "model": "stock.stocklocation",
            "required": False,
        },
    }

    def setup_urls(self):
        from .urls import urlpatterns
        return urlpatterns

    def get_ui_panels(self, request, context, **kwargs):
        context = context or {}
        target_model = context.get("target_model")
        target_id = context.get("target_id")

        if target_model not in {"purchaseorder", "stockitem"} or target_id is None:
            return []

        return [{
            "key": "supplier-return-panel",
            "title": _("Supplier Returns"),
            "icon": "ti:truck-return:outline",
            "source": self.plugin_static_file("supplier_return.js:renderSupplierReturnPanel"),
            "context": {"target_model": target_model, "target_id": target_id},
        }]
