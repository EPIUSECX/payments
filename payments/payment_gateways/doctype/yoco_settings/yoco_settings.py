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
            "Yoco-" + self.name,
            settings="Yoco Settings",
            controller=self.name,
        )
        call_hook_method("payment_gateway_enabled", gateway="Yoco-" + self.name)

    @frappe.whitelist()
    def test_connection(self):
        """Test the connection to the Yoco API."""
        import requests

        secret_key = self.get_password(fieldname="secret_key", raise_exception=False)
        if not secret_key:
            return {"status": "error", "message": "Please set the Secret Key."}

        # Use the correct Yoco API endpoint for testing credentials
        test_url = "https://payments.yoco.com/api/webhooks" # Correct endpoint for testing

        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(test_url, headers=headers, timeout=10) # Use GET method
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            # Assuming a successful response indicates a valid connection
            return {"status": "success", "message": "Connection successful!"}

        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": f"Connection failed: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred: {e}"}


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

        success_url_path = kwargs.get("return_url", "payment-success")
        query_params = {
            "doctype": kwargs.get("reference_doctype"),
            "docname": kwargs.get("reference_docname")
        }
        encoded_query_params = urlencode(query_params)
        full_success_url = f"{get_url(success_url_path)}?{encoded_query_params}"

        payload = {
            "amount": amount_in_cents,
            "currency": kwargs.get("currency"), # Should be ZAR based on validation
            "cancelUrl": get_url(kwargs.get("cancel_url", "payment-failed")),
            "successUrl": full_success_url, # Use return_url as successUrl with doctype and docname
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
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            response_json = response.json()

            # According to the logged response, Yoco returns redirectUrl directly
            # and a status like "created" if successful.
            # There isn't a top-level "success": true key.
            redirect_url = response_json.get("redirectUrl")
            yoco_status = response_json.get("status")

            if redirect_url and yoco_status == "created":
                return redirect_url
            else:
                error_detail = f"Yoco checkout session creation did not return a valid redirectUrl or status. Status: {yoco_status}, Redirect URL: {redirect_url}. Full Response: {response_json}"
                frappe.log_error(error_detail, "Yoco Integration Error")
                return get_url(kwargs.get("cancel_url", "payment-failed"))

        except requests.exceptions.RequestException as e:
            error_message = f"Yoco Checkout Request Error: {str(e)}"
            if e.response is not None:
                error_message += f" | Response Status: {e.response.status_code} | Response Text: {e.response.text}"
            frappe.log_error(f"{error_message}\n{frappe.get_traceback()}", "Yoco Checkout Request Error")
            return get_url(kwargs.get("cancel_url", "payment-failed")) # Redirect to failure page on error
        except Exception as e: # Catching generic Exception to log it more verbosely
            frappe.log_error(f"Unexpected Yoco Integration Error: {str(e)}\n{frappe.get_traceback()}", "Yoco Integration Error")
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
