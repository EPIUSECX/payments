# Copyright (c) 2024, [Your Name] and contributors
# License: MIT. See LICENSE

import frappe
import hmac
import hashlib
import json

@frappe.whitelist(allow_guest=True)
def handle_webhook():
    """
    Handle webhook notifications from Paystack.
    """
    request_body = frappe.request.data
    paystack_signature = frappe.request.headers.get("x-paystack-signature")
    settings = frappe.get_doc("Paystack Settings")
    secret_key = settings.get_password(fieldname="secret_key", raise_exception=False)

    if not verify_signature(request_body, paystack_signature, secret_key):
        frappe.log_error("Paystack webhook signature verification failed", "Paystack Webhook Error")
        frappe.throw("Invalid signature", frappe.PermissionError)

    try:
        payload = json.loads(request_body)
        event = payload.get("event")
        data = payload.get("data")

        if event == "charge.success":
            payment_request_id = data.get("metadata", {}).get("reference_docname")
            if payment_request_id:
                payment_request = frappe.get_doc("Payment Request", payment_request_id)
                sales_invoice_id = payment_request.reference_name
                if sales_invoice_id:
                    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_id)
                    sales_invoice.run_method("on_payment_authorized", "Completed")
        else:
            frappe.log_error(f"Paystack Webhook: Received unhandled event type '{event}'", "Paystack Webhook Info")

        frappe.response["message"] = "Webhook received successfully"

    except json.JSONDecodeError:
        frappe.log_error("Paystack webhook payload is not valid JSON", "Paystack Webhook Error")
        frappe.throw("Invalid JSON payload", frappe.ValidationError)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Error processing Paystack webhook")
        frappe.throw("Error processing webhook", frappe.ValidationError)

def verify_signature(request_body, paystack_signature, secret_key):
    """
    Verify the Paystack webhook signature.
    """
    hashed = hmac.new(
        secret_key.encode('utf-8'),
        request_body,
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(hashed, paystack_signature)

