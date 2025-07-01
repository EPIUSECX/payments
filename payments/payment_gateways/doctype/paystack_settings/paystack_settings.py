# Copyright (c) 2024, [Your Name] and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.utils import get_url
from urllib.parse import urlencode

class PaystackSettings(Document):
    def on_update(self):
        from payments.utils import create_payment_gateway
        from frappe.utils import call_hook_method

        create_payment_gateway(
            "Paystack-" + self.name,
            settings="Paystack Settings",
            controller=self.name,
        )
        call_hook_method("payment_gateway_enabled", gateway="Paystack-" + self.name)

    def validate_transaction_currency(self, currency):
        supported_currencies = ['NGN', 'GHS', 'ZAR', 'USD'] # As per example
        if currency not in supported_currencies:
            frappe.throw(f"{currency} is not supported by Paystack.")

    def validate_minimum_transaction_amount(self, currency, amount):
        # Define minimum amounts per currency (in base unit, e.g., kobo for NGN)
        # TODO: Confirm actual minimum amounts from Paystack documentation
        minimum_amounts = {
            'NGN': 100,   # ₦1.00
            'GHS': 100,   # GH₵1.00
            'ZAR': 100,   # R1.00
            'USD': 100,   # $1.00
        }

        if currency not in minimum_amounts:
             # Should not happen if validate_transaction_currency is called first
             frappe.throw(f"Minimum amount not defined for currency {currency}.")

        # Define minimum amounts per currency (in the smallest currency unit)
        # TODO: Confirm actual minimum amounts from Paystack documentation
        minimum_amounts_subunit = {
            'NGN': 100,   # ₦1.00
            'GHS': 100,   # GH₵1.00
            'ZAR': 100,   # R1.00
            'USD': 100,   # $1.00
        }

        if currency not in minimum_amounts_subunit:
             # Should not happen if validate_transaction_currency is called first
             frappe.throw(f"Minimum amount not defined for currency {currency}.")

        # Convert amount to the smallest currency unit for comparison
        amount_in_lowest_denomination = int(amount * 100) # Multiply by 100 for supported currencies

        if amount_in_lowest_denomination < minimum_amounts_subunit[currency]:
            frappe.throw(f"The minimum transaction amount for {currency} is {minimum_amounts_subunit[currency]/100:.2f}.")

    def get_payment_url(self, **kwargs):
        from frappe.integrations.utils import create_request_log

        integration_request = create_request_log(kwargs, service_name="Paystack")
        return get_url(f"./paystack_checkout?token={integration_request.name}")

    def create_request(self, data):
        import requests
        from frappe.integrations.utils import create_request_log
 
        self.data = frappe._dict(data)
 
        # TODO: Confirm Paystack API endpoint for initializing transactions
        paystack_url = "https://api.paystack.co/transaction/initialize"
        if self.test_mode:
             # Paystack uses the same endpoint for test and live, but different keys
             pass # No change to URL for test mode

        headers = {
            "Authorization": f"Bearer {self.get_password(fieldname='secret_key', raise_exception=False)}",
            "Content-Type": "application/json"
        }

        # Prepare data for Paystack API call
        # Amount should be in the smallest currency unit (e.g., kobo for NGN, cents for USD)
        # Multiply by 100 for the supported currencies as per documentation
        amount_in_lowest_denomination = int(self.data.amount * 100)

        payload = {
            "email": self.data.payer_email,
            "amount": amount_in_lowest_denomination,
            "callback_url": get_url(self.data.get("return_url")), # Use return_url as callback
            "metadata": {
                "reference_doctype": self.data.reference_doctype,
                "reference_docname": self.data.reference_docname,
                "payer_name": self.data.payer_name,
                "item_name": self.data.item_name,
                "item_description": self.data.item_description,
                # Add other relevant data from self.data if needed
            },
            # Add other required parameters based on Paystack documentation
            "currency": self.data.currency, # TODO: Validate supported currencies
            "reference": self.data.reference_docname + "-" + frappe.generate_random_string(5), # Generate a unique reference
        }

        try:
            self.integration_request = create_request_log(payload, service_name="Paystack", url=paystack_url)
            response = requests.post(paystack_url, headers=headers, json=payload)
            response.raise_for_status() # Raise an exception for bad status codes
            response_json = response.json()

            if response_json.get("status") is True:
                authorization_url = response_json["data"]["authorization_url"]
                self.integration_request.db_set("status", "Initiated", update_modified=False) # Assuming "Initiated" status exists
                self.integration_request.db_set("response", response.text, update_modified=False)
                frappe.db.commit()

                return {
                    "redirect_to": authorization_url,
                    "integration_request": self.integration_request.name
                }
            else:
                self.integration_request.db_set("status", "Failed", update_modified=False)
                self.integration_request.db_set("response", response.text, update_modified=False)
                frappe.db.commit()
                frappe.log_error(f"Paystack transaction initialization failed: {response_json.get('message')}", "Paystack Integration Error")
                return {
                    "redirect_to": frappe.redirect_to_message(
                        _("Payment Failed"),
                        _("Paystack transaction initialization failed. Please try again or contact support."),
                    ),
                    "status": 400,
                }

        except requests.exceptions.RequestException as e:
            if hasattr(self, 'integration_request') and self.integration_request:
                 self.integration_request.db_set("status", "Error", update_modified=False)
                 self.integration_request.db_set("response", str(e), update_modified=False)
                 frappe.db.commit()
            frappe.log_error(frappe.get_traceback(), "Paystack Integration Request Error")
            return {
                "redirect_to": frappe.redirect_to_message(
                    _("Server Error"),
                    _("There was an error initiating the payment with Paystack. Please try again or contact support."),
                ),
                "status": 500,
            }
        except Exception:
            if hasattr(self, 'integration_request') and self.integration_request:
                 self.integration_request.db_set("status", "Error", update_modified=False)
                 frappe.db.commit()
            frappe.log_error(frappe.get_traceback(), "Paystack Integration Error")
            return {
                "redirect_to": frappe.redirect_to_message(
                    _("Server Error"),
                    _("An unexpected error occurred during Paystack payment initiation. Please try again or contact support."),
                ),
                "status": 500,
            }


    def finalize_request(self):
        # This method is called when the user is redirected back from Paystack
        # The actual payment status update will happen via webhook
        # We can use this to show a pending message or redirect to a status page

        # TODO: Implement logic to show a pending message or redirect to a status page
        # based on query parameters from Paystack redirect (if any)

        redirect_to = self.data.get("redirect_to") or None
        redirect_message = self.data.get("redirect_message") or None
        status = self.integration_request.status # Assuming status is set in create_request or webhook

        # For now, redirect to a pending page or similar
        redirect_url = "payment-pending" # Assuming a payment-pending page exists

        if redirect_to and "?" in redirect_url:
            redirect_url += "&" + urlencode({"redirect_to": redirect_to})
        else:
            redirect_url += "?" + urlencode({"redirect_to": redirect_to})

        if redirect_message:
            redirect_url += "&" + urlencode({"redirect_message": redirect_message})

        # Add any relevant query parameters from the Paystack redirect to the final URL
        # Example: if Paystack adds a 'trxref' parameter
        # trxref = frappe.request.args.get("trxref")
        # if trxref:
        #     redirect_url += "&" + urlencode({"trxref": trxref})


        return {"redirect_to": redirect_url, "status": status}
