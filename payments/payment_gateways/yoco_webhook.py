# Copyright (c) 2024, [Your Name] and contributors
# License: MIT. See LICENSE

import frappe
import json
import hmac
import hashlib
import os

@frappe.whitelist(allow_guest=True)
def handle_webhook():
    """
    Handle webhook notifications from Yoco.
    This is the single entry point for all Yoco webhooks.
    """
    log_path = os.path.join(frappe.utils.get_bench_path(), "logs", "yoco_webhook.log")
    with open(log_path, "a") as f:
        f.write(f"--- New Yoco Webhook Request ---\n")
        f.write(f"Headers: {frappe.request.headers}\n")
        f.write(f"Body: {frappe.request.data}\n")

    request_body = frappe.request.data
    yoco_signature = frappe.request.headers.get("X-Yoco-Signature")
    settings = frappe.get_doc("Yoco Settings")
    webhook_secret = settings.get_password(fieldname="webhook_secret", raise_exception=False)

    if not verify_signature(request_body, yoco_signature, webhook_secret):
        with open(log_path, "a") as f:
            f.write("Signature verification failed.\n")
        frappe.log_error("Yoco webhook signature verification failed", "Yoco Webhook Error")
        frappe.throw("Invalid signature", frappe.PermissionError)

    try:
        payload = json.loads(request_body)
        event_type = payload.get("type")
        data = payload.get("data", {}).get("object", {})

        with open(log_path, "a") as f:
            f.write(f"Payload: {json.dumps(payload, indent=4)}\n")

        if event_type == "charge.succeeded":
            payment_request_id = data.get("metadata", {}).get("reference_docname")
            if payment_request_id:
                pr = frappe.get_doc("Payment Request", payment_request_id)
                pr.run_method("set_as_paid")
        else:
            # Log other events for now, can be handled later
            frappe.log_error(f"Yoco Webhook: Received unhandled event type '{event_type}'", "Yoco Webhook Info")

        frappe.response["message"] = "Webhook received successfully"

    except json.JSONDecodeError:
        with open(log_path, "a") as f:
            f.write("Error: Invalid JSON payload.\n")
        frappe.log_error("Yoco webhook payload is not valid JSON", "Yoco Webhook Error")
        frappe.throw("Invalid JSON payload", frappe.ValidationError)
    except Exception as e:
        with open(log_path, "a") as f:
            f.write(f"Error processing webhook: {e}\n")
            f.write(frappe.get_traceback())
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

