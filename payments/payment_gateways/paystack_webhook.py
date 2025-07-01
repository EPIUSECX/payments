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
            create_payment_entry_from_webhook(data)
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

def create_payment_entry_from_webhook(data):
    """
    Create and submit a Payment Entry in Frappe based on Paystack webhook data.
    """
    metadata = data.get("metadata", {})
    reference_doctype = metadata.get("reference_doctype")
    reference_docname = metadata.get("reference_docname")
    paystack_reference = data.get("reference")

    if not all([reference_doctype, reference_docname, paystack_reference]):
        frappe.log_error("Paystack webhook metadata missing required fields for Payment Entry creation.", "Paystack Webhook Error")
        return

    # Idempotency Check
    if frappe.db.exists("Payment Entry", {"reference_no": paystack_reference, "docstatus": 1}):
        frappe.log_error(f"Duplicate Paystack webhook received for reference: {paystack_reference}", "Paystack Webhook Info")
        return

    try:
        sales_invoice = frappe.get_doc(reference_doctype, reference_docname)
        
        payment_gateway_account = frappe.db.get_value(
            "Payment Gateway Account", {"payment_gateway": "Paystack"}, "payment_account"
        )
        
        if not payment_gateway_account:
            frappe.log_error("No Payment Account found for Paystack Payment Gateway.", "Paystack Configuration Error")
            return

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.mode_of_payment = "Paystack"
        pe.party_type = "Customer"
        pe.party = sales_invoice.customer
        pe.paid_amount = data.get("amount") / 100  # Paystack sends amount in kobo
        pe.received_amount = data.get("amount") / 100
        pe.paid_to = payment_gateway_account
        pe.reference_no = paystack_reference
        pe.reference_date = frappe.utils.nowdate()
        
        pe.append("references", {
            "reference_doctype": reference_doctype,
            "reference_name": reference_docname,
            "bill_no": sales_invoice.bill_no,
            "due_date": sales_invoice.due_date,
            "total_amount": sales_invoice.grand_total,
            "outstanding_amount": sales_invoice.outstanding_amount,
            "allocated_amount": data.get("amount") / 100,
        })

        pe.insert(ignore_permissions=True)
        pe.submit()

        frappe.db.commit()
        frappe.log_error(f"Paystack Webhook: Payment Entry {pe.name} created for {reference_doctype} {reference_docname}", "Paystack Webhook Success")

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error creating Payment Entry for {reference_doctype} {reference_docname} from Paystack webhook")
        frappe.db.rollback()
        raise e
