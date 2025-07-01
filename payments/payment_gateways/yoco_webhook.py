# Copyright (c) 2024, [Your Name] and contributors
# License: MIT. See LICENSE

import frappe
import json
import hmac
import hashlib

@frappe.whitelist(allow_guest=True)
def handle_webhook():
    """
    Handle webhook notifications from Yoco.
    This is the single entry point for all Yoco webhooks.
    """
    request_body = frappe.request.data
    yoco_signature = frappe.request.headers.get("X-Yoco-Signature")
    settings = frappe.get_doc("Yoco Settings")
    webhook_secret = settings.get_password(fieldname="webhook_secret", raise_exception=False)

    if not verify_signature(request_body, yoco_signature, webhook_secret):
        frappe.log_error("Yoco webhook signature verification failed", "Yoco Webhook Error")
        frappe.throw("Invalid signature", frappe.PermissionError)

    try:
        payload = json.loads(request_body)
        event_type = payload.get("type")
        data = payload.get("data", {}).get("object", {})

        if event_type == "charge.succeeded":
            create_payment_entry_from_webhook(data)
        else:
            # Log other events for now, can be handled later
            frappe.log_error(f"Yoco Webhook: Received unhandled event type '{event_type}'", "Yoco Webhook Info")

        frappe.response["message"] = "Webhook received successfully"

    except json.JSONDecodeError:
        frappe.log_error("Yoco webhook payload is not valid JSON", "Yoco Webhook Error")
        frappe.throw("Invalid JSON payload", frappe.ValidationError)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Error processing Yoco webhook")
        frappe.throw("Error processing webhook", frappe.ValidationError)

def verify_signature(request_body, signature, secret):
    """Verify the signature of the incoming webhook."""
    if not signature:
        return False
    
    generated_signature = hmac.new(
        secret.encode('utf-8'),
        request_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(generated_signature, signature)

def create_payment_entry_from_webhook(data):
    """
    Create and submit a Payment Entry in Frappe based on Yoco webhook data.
    """
    metadata = data.get("metadata", {})
    reference_doctype = metadata.get("reference_doctype")
    reference_docname = metadata.get("reference_docname")
    yoco_charge_id = data.get("id")

    if not all([reference_doctype, reference_docname, yoco_charge_id]):
        frappe.log_error("Yoco webhook metadata missing required fields for Payment Entry creation.", "Yoco Webhook Error")
        return

    # Idempotency Check: Ensure we don't process the same charge twice
    if frappe.db.exists("Payment Entry", {"reference_no": yoco_charge_id, "docstatus": 1}):
        frappe.log_error(f"Duplicate Yoco webhook received for charge ID: {yoco_charge_id}", "Yoco Webhook Info")
        return

    try:
        sales_invoice = frappe.get_doc(reference_doctype, reference_docname)
        
        payment_gateway_account = frappe.db.get_value(
            "Payment Gateway Account", {"payment_gateway": "Yoco"}, "payment_account"
        )
        
        if not payment_gateway_account:
            frappe.log_error("No Payment Account found for Yoco Payment Gateway.", "Yoco Configuration Error")
            return

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.mode_of_payment = "Yoco"
        pe.party_type = "Customer"
        pe.party = sales_invoice.customer
        pe.paid_amount = data.get("amount") / 100  # Yoco sends amount in cents
        pe.received_amount = data.get("amount") / 100
        pe.paid_to = payment_gateway_account
        pe.reference_no = yoco_charge_id
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
        frappe.log_error(f"Yoco Webhook: Payment Entry {pe.name} created for {reference_doctype} {reference_docname}", "Yoco Webhook Success")

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error creating Payment Entry for {reference_doctype} {reference_docname} from Yoco webhook")
        frappe.db.rollback()
        raise e
