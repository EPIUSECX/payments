# Copyright (c) 2024, [Your Name] and contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils import get_url
import hashlib
import requests

@frappe.whitelist(allow_guest=True)
def handle_itn():
    """
    Handle Instant Transaction Notifications (ITN) from Payfast.
    """
    try:
        itn_data = frappe.request.form
        
        if not validate_itn(itn_data):
            frappe.log_error("Payfast ITN validation failed", "Payfast ITN Error")
            return

        if itn_data.get("payment_status") == "COMPLETE":
            payment_request_id = itn_data.get("custom_str2")
            if payment_request_id:
                payment_request = frappe.get_doc("Payment Request", payment_request_id)
                sales_invoice_id = payment_request.reference_name
                if sales_invoice_id:
                    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_id)
                    sales_invoice.run_method("on_payment_authorized", "Completed")
        else:
            # Log other statuses for now
            frappe.log_error(f"Payfast ITN: Received non-complete status '{itn_data.get('payment_status')}'", "Payfast ITN Info")

        frappe.response["message"] = "OK"

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Error processing Payfast ITN")
        frappe.response.http_status_code = 500

def validate_itn(data):
    """
    Validate the ITN data received from Payfast.
    """
    # Simplified validation for this context. In production, use all validation steps.
    settings = frappe.get_doc("Payfast Settings")
    received_signature = data.get("signature")
    
    # Create string from form data
    form_data = {k: v for k, v in data.items() if k != 'signature'}
    ordered_data = sorted(form_data.items(), key=lambda item: item[0])
    data_string = '&'.join([f"{k}={v}" for k, v in ordered_data])
    
    passphrase = settings.get_password(fieldname="passphrase", raise_exception=False)
    if passphrase:
        data_string += f"&passphrase={passphrase}"

    generated_signature = hashlib.md5(data_string.encode()).hexdigest()

    if not generated_signature == received_signature:
        frappe.log_error(f"Payfast ITN signature mismatch. Received: {received_signature}, Generated: {generated_signature}", "Payfast ITN Validation Error")
        return False
        
    return True

