# Copyright (c) 2024, [Your Name] and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.utils import get_url
from urllib.parse import urlencode

class PayfastSettings(Document):
    def on_update(self):
        from payments.utils import create_payment_gateway
        from frappe.utils import call_hook_method

        create_payment_gateway(
            "Payfast-" + self.name,
            settings="Payfast Settings",
            controller=self.name,
        )
        call_hook_method("payment_gateway_enabled", gateway="Payfast-" + self.name)

    def validate_transaction_currency(self, currency):
        # Basic currency validation: only ZAR supported in this basic implementation
        if currency != "ZAR":
             frappe.throw(_("Payfast only supports transactions in ZAR.")) # TODO: Implement MCP currency validation if needed

    def validate_minimum_transaction_amount(self, currency, amount):
        # Basic minimum amount validation
        minimum_amount = 5.00 # R5.00 as per documentation example
        if flt(amount) < minimum_amount:
            frappe.throw(_("For currency {0}, the minimum transaction amount should be {1}").format(currency, minimum_amount))

    def get_payment_url(self, **kwargs):
        from frappe.integrations.utils import create_request_log

        integration_request = create_request_log(kwargs, service_name="Payfast")
        return get_url(f"./payfast_checkout?token={integration_request.name}")

    def create_request(self, data):
        from frappe.integrations.utils import create_request_log

        self.data = frappe._dict(data)

        # Prepare data for Payfast based on required parameters
        payfast_data = {
            "amount": self.data.amount,
            "item_name": self.data.item_name or f"Payment for {self.data.reference_doctype}: {self.data.reference_docname}",
            "item_description": self.data.item_description,
            "return_url": self.data.get("return_url"),
            "cancel_url": self.data.get("cancel_url"),
            "notify_url": self.data.get("notify_url"),
            "payer_name": self.data.payer_name,
            "payer_email": self.data.payer_email,
            "reference_docname": self.data.reference_docname,
            "reference_doctype": self.data.reference_doctype,
            # Add other relevant data from self.data if needed by get_payment_url
        }

        self.integration_request = create_request_log(payfast_data, service_name="Payfast")

        # The actual redirection happens via get_payment_url, which is called after create_request
        # We just need to return the necessary info for the redirect
        return {
            "redirect_to": self.get_payment_url(**payfast_data),
            "integration_request": self.integration_request.name
        }

    def finalize_request(self):
        # TODO: Implement Payfast ITN (Instant Transaction Notification) handler for server-side status updates
        redirect_to = self.data.get("redirect_to") or None
        redirect_message = self.data.get("redirect_message") or None
        status = self.integration_request.status # Assuming status is set in create_request or an ITN handler

        if status == "Completed": # Assuming "Completed" status indicates success
            if self.data.reference_doctype and self.data.reference_docname:
                custom_redirect_to = None
                try:
                    # Call on_payment_authorized on the reference document
                    custom_redirect_to = frappe.get_doc(
                        self.data.reference_doctype, self.data.reference_docname
                    ).run_method("on_payment_authorized", status)
                except Exception:
                    frappe.log_error(frappe.get_traceback())

                if custom_redirect_to:
                    redirect_to = custom_redirect_to

                redirect_url = f"payment-success?doctype={self.data.reference_doctype}&docname={self.data.reference_docname}"

            # TODO: Check if Payfast provides a specific success redirect URL
            # if self.redirect_url:
            #     redirect_url = self.redirect_url
            #     redirect_to = None
        else:
            redirect_url = "payment-failed" # Assuming any other status is a failure

        if redirect_to and "?" in redirect_url:
            redirect_url += "&" + urlencode({"redirect_to": redirect_to})
        else:
            redirect_url += "?" + urlencode({"redirect_to": redirect_to})

        if redirect_message:
            redirect_url += "&" + urlencode({"redirect_message": redirect_message})

        return {"redirect_to": redirect_url, "status": status}
