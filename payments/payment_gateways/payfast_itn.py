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
            create_payment_entry_from_itn(itn_data)
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

def create_payment_entry_from_itn(data):
    """
    Create and submit a Payment Entry in Frappe based on Payfast ITN data.
    """
    reference_doctype = data.get("custom_str1")
    reference_docname = data.get("custom_str2")
    payfast_payment_id = data.get("pf_payment_id")

    if not all([reference_doctype, reference_docname, payfast_payment_id]):
        frappe.log_error("Payfast ITN missing required fields for Payment Entry creation.", "Payfast ITN Error")
        return

    # Idempotency Check
    if frappe.db.exists("Payment Entry", {"reference_no": payfast_payment_id, "docstatus": 1}):
        frappe.log_error(f"Duplicate Payfast ITN received for payment ID: {payfast_payment_id}", "Payfast ITN Info")
        return

    try:
        sales_invoice = frappe.get_doc(reference_doctype, reference_docname)
        
        payment_gateway_account = frappe.db.get_value(
            "Payment Gateway Account", {"payment_gateway": "Payfast"}, "payment_account"
        )
        
        if not payment_gateway_account:
            frappe.log_error("No Payment Account found for Payfast Payment Gateway.", "Payfast Configuration Error")
            return

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.mode_of_payment = "Payfast"
        pe.party_type = "Customer"
        pe.party = sales_invoice.customer
        pe.paid_amount = data.get("amount_gross")
        pe.received_amount = data.get("amount_net")
        pe.paid_to = payment_gateway_account
        pe.reference_no = payfast_payment_id
        pe.reference_date = frappe.utils.nowdate()
        
        pe.append("references", {
            "reference_doctype": reference_doctype,
            "reference_name": reference_docname,
            "bill_no": sales_invoice.bill_no,
            "due_date": sales_invoice.due_date,
            "total_amount": sales_invoice.grand_total,
            "outstanding_amount": sales_invoice.outstanding_amount,
            "allocated_amount": data.get("amount_gross"),
        })

        pe.insert(ignore_permissions=True)
        pe.submit()

        frappe.db.commit()
        frappe.log_error(f"Payfast ITN: Payment Entry {pe.name} created for {reference_doctype} {reference_docname}", "Payfast ITN Success")

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error creating Payment Entry for {reference_doctype} {reference_docname} from Payfast ITN")
        frappe.db.rollback()
        raise e
