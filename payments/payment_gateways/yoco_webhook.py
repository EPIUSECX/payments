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
    """
    request_body = frappe.request.data # Get raw POST data
    yoco_signature = frappe.request.headers.get("X-Yoco-Signature")
    settings = frappe.get_doc("Yoco Settings")
    webhook_secret = settings.get_password(fieldname="webhook_secret", raise_exception=False) # Assuming a 'webhook_secret' field in Yoco Settings

    # Implement Yoco webhook signature verification
    if not yoco_signature:
        frappe.log_error("Yoco webhook received without signature", "Yoco Webhook Error")
        frappe.throw("Signature missing", frappe.PermissionError)

    # Concatenate raw request body with webhook secret
    signed_payload = request_body + webhook_secret.encode('utf-8')

    # Compute the SHA256 HMAC
    generated_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        request_body,
        hashlib.sha256
    ).hexdigest()

    # Compare the generated signature with the received signature
    if not hmac.compare_digest(generated_signature, yoco_signature):
        frappe.log_error(f"Yoco webhook signature verification failed. Received: {yoco_signature}, Generated: {generated_signature}", "Yoco Webhook Error")
        frappe.throw("Invalid signature", frappe.PermissionError)


    try:
        payload = json.loads(request_body)
        event = payload.get("type") # Yoco uses 'type' for event type
        data = payload.get("data")

        # Process Yoco webhook events and update payment status
        if event == "charge.succeeded":
            update_payment_status(data, "Paid") # Use "Paid" status for compatibility with Payment Request
        elif event == "charge.failed":
            update_payment_status(data, "Failed")
        elif event == "charge.refunded":
            update_payment_status(data, "Refunded") # Assuming "Refunded" status exists in Frappe
        # TODO: Handle other relevant Yoco webhook events if necessary

        frappe.response["message"] = "Webhook received successfully"

    except json.JSONDecodeError:
        frappe.log_error("Yoco webhook payload is not valid JSON", "Yoco Webhook Error")
        frappe.throw("Invalid JSON payload", frappe.ValidationError)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Error processing Yoco webhook")
        frappe.throw("Error processing webhook", frappe.ValidationError)


def update_payment_status(data, status):
    """
    Update the payment status in Frappe based on Yoco webhook data.
    """
    # Extract reference details from Yoco webhook data (from metadata)
    metadata = data.get("metadata")
    if not metadata:
        frappe.log_error("Yoco webhook data missing metadata for status update", "Yoco Webhook Error")
        return

    reference_doctype = metadata.get("reference_doctype")
    reference_docname = metadata.get("reference_docname")
    yoco_charge_id = data.get("id") # Yoco Charge ID

    if not reference_doctype or not reference_docname:
        frappe.log_error("Yoco webhook metadata missing reference doctype or docname for status update", "Yoco Webhook Error")
        return

    try:
        doc = frappe.get_doc(reference_doctype, reference_docname)

        # Update document status
        doc.run_method("on_payment_authorized", status) # Call the hook on the document

        # Optionally store Yoco Charge ID on the document
        if hasattr(doc, 'yoco_charge_id'): # Assuming a field named 'yoco_charge_id' exists
             doc.yoco_charge_id = yoco_charge_id

        doc.save(ignore_permissions=True) # Save the document with updated status
        frappe.db.commit()
        frappe.log_main_tx(f"Yoco Webhook: Payment {status} for {reference_doctype} {reference_docname} (Yoco ID: {yoco_charge_id})")

    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Error updating payment status for {reference_doctype} {reference_docname} from Yoco webhook")
        frappe.db.rollback() # Rollback changes in case of error
