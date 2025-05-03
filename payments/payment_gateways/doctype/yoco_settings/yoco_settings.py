# Copyright (c) 2024, [Your Name] and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.utils import get_url
from urllib.parse import urlencode

class YocoSettings(Document):
    def on_update(self):
        from payments.utils import create_payment_gateway
        from frappe.utils import call_hook_method

        create_payment_gateway(
            "Yoco-" + self.gateway_name,
            settings="Yoco Settings",
            controller="Yoco Settings",
        )
        call_hook_method("payment_gateway_enabled", gateway="Yoco-" + self.gateway_name)

    def validate_transaction_currency(self, currency):
        # Yoco primarily supports ZAR
        if currency != "ZAR":
             frappe.throw(_("Yoco primarily supports transactions in ZAR.")) # TODO: Confirm if other currencies are supported and add validation

    def validate_minimum_transaction_amount(self, currency, amount):
        # Minimum transaction amount is typically R1.00 (100 cents)
        minimum_amount_cents = 100 # R1.00 in cents

        # Convert amount to cents for comparison
        amount_in_cents = int(amount * 100) # Assuming currency requires multiplying by 100

        if amount_in_cents < minimum_amount_cents:
            frappe.throw(_("For currency {0}, the minimum transaction amount should be {1}").format(currency, minimum_amount_cents / 100.0))

    def get_payment_url(self, **kwargs):
        import requests
        from frappe.integrations.utils import create_request_log

        # Yoco Checkout API endpoint for creating checkout sessions
        yoco_checkout_url = "https://payments.yoco.com/api/checkouts"

        headers = {
            "Authorization": f"Bearer {self.get_password(fieldname='secret_key', raise_exception=False)}",
            "Content-Type": "application/json"
        }

        # Prepare data for Yoco Checkout API call
        # Amount should be in cents (for ZAR)
        amount_in_cents = int(kwargs.get("amount") * 100) # Assuming amount is in major unit

        payload = {
            "amount": amount_in_cents,
            "currency": kwargs.get("currency"), # Should be ZAR based on validation
            "cancelUrl": get_url(kwargs.get("cancel_url", "payment-failed")),
            "successUrl": get_url(kwargs.get("return_url", "payment-success")), # Use return_url as successUrl
            "failureUrl": get_url(kwargs.get("cancel_url", "payment-failed")), # Use cancel_url as failureUrl
            "metadata": {
                "reference_doctype": kwargs.get("reference_doctype"),
                "reference_docname": kwargs.get("reference_docname"),
                "payer_name": kwargs.get("payer_name"),
                "payer_email": kwargs.get("payer_email"),
                "item_name": kwargs.get("item_name"),
                "item_description": kwargs.get("item_description"),
                # Add other relevant data from kwargs if needed
            },
            # Add other required parameters based on Yoco documentation
        }

        try:
            # Log the request to the Checkout API
            create_request_log(payload, service_name="Yoco Checkout", url=yoco_checkout_url)
            response = requests.post(yoco_checkout_url, headers=headers, json=payload)
            response.raise_for_status() # Raise an exception for bad status codes
            response_json = response.json()

            if response_json.get("success") is True: # Confirm success field from docs
                redirect_url = response_json["data"]["redirectUrl"] # Confirm redirectUrl field from docs
                return redirect_url
            else:
                frappe.log_error(f"Yoco checkout session creation failed: {response_json.get('message')}", "Yoco Integration Error")
                return get_url(kwargs.get("cancel_url", "payment-failed")) # Redirect to failure page on error

        except requests.exceptions.RequestException as e:
            frappe.log_error(frappe.get_traceback(), "Yoco Checkout Request Error")
            return get_url(kwargs.get("cancel_url", "payment-failed")) # Redirect to failure page on error
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Yoco Integration Error")
            return get_url(kwargs.get("cancel_url", "payment-failed")) # Redirect to failure page on error


    def create_request(self, data):
        # In this redirect flow, the main payment initiation happens in get_payment_url.
        # This method might be used for initial logging or setup before calling get_payment_url.
        # For now, we can just log the initial request data.
        from frappe.integrations.utils import create_request_log
        self.data = frappe._dict(data)
        self.integration_request = create_request_log(self.data, service_name="Yoco Payment Request")
        frappe.db.commit()
        # The actual redirect will be handled by Frappe after calling get_payment_url
        return {
            "integration_request": self.integration_request.name
        }


    def finalize_request(self):
        # This method is called after the user returns from Yoco.
        # The actual payment status update is handled by the webhook.
        # This method can be used to display a pending message or redirect to a status page.
        # TODO: Determine the exact role of finalize_request in the Yoco redirect flow.

        redirect_to = self.data.get("redirect_to") or None
        redirect_message = self.data.get("redirect_message") or None
        status = self.integration_request.status # Assuming status is set by webhook

        # For now, redirect to a pending page or similar
        redirect_url = "payment-pending" # Assuming a payment-pending page exists

        if redirect_to and "?" in redirect_url:
            redirect_url += "&" + urlencode({"redirect_to": redirect_to})
        else:
            redirect_url += "?" + urlencode({"redirect_to": redirect_to})

        if redirect_message:
            redirect_url += "&" + urlencode({"redirect_message": redirect_message})

        # Add any relevant query parameters from the Yoco redirect to the final URL
        # TODO: Consult Yoco docs for redirect query parameters

        return {"redirect_to": redirect_url, "status": status}
