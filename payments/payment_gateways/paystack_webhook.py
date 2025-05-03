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
    settings = frappe.get_doc("Paystack Settings")
    secret_key = settings.get_password(fieldname="secret_key", raise_exception=False)
    request_body = frappe.request.data # Get raw POST data
    paystack_signature = frappe.request.headers.get("x-paystack-signature")

    # TODO: Implement IP whitelisting for Paystack webhooks
    # Get official Paystack webhook IP addresses and verify request origin
    # Example:
    # paystack_webhook_ips = ["xxx.xxx.xxx.xxx", "yyy.yyy.yyy.yyy"] # Replace with actual IPs
    # if frappe.request.remote_addr not in paystack_webhook_ips:
    #     frappe.log_error(f"Paystack webhook received from invalid IP: {frappe.request.remote_addr}", "Paystack Webhook Error")
    #     frappe.throw("Invalid source IP", frappe.PermissionError)
    frappe.log_warning("Paystack webhook IP verification skipped. TODO: Implement IP verification.", "Paystack Webhook Warning")


    # 1. Verify webhook signature
    if not verify_signature(request_body, paystack_signature, secret_key):
        frappe.log_error("Paystack webhook signature verification failed", "Paystack Webhook Error")
        frappe.throw("Invalid signature", frappe.PermissionError)

    # 2. Process webhook event
    try:
        payload = json.loads(request_body)
        event = payload.get("event")
        data = payload.get("data")

        if event == "charge.success":
            update_payment_status(data, "Completed")
        elif event == "charge.failed":
            update_payment_status(data, "Failed")
        elif event == "transfer.success":
            # TODO: Implement handling for successful transfers
            frappe.log_main_tx(f"Paystack Webhook: Transfer successful for reference {data.get('reference')}")
        elif event == "transfer.failed":
            # TODO: Implement handling for failed transfers
            frappe.log_main_tx(f"Paystack Webhook: Transfer failed for reference {data.get('reference')}")
        elif event == "subscription.create":
            # TODO: Implement handling for subscription creation
            frappe.log_main_tx(f"Paystack Webhook: Subscription created for customer {data.get('customer', {}).get('customer_code')}")
        elif event == "invoice.create":
            # TODO: Implement handling for invoice creation
            frappe.log_main_tx(f"Paystack Webhook: Invoice created for customer {data.get('customer', {}).get('customer_code')}")
        elif event == "invoice.payment_failed":
            # TODO: Implement handling for failed invoice payments
            update_payment_status(data, "Failed") # Assuming failed invoice payment maps to Failed status
        elif event == "invoice.payment_successful":
            # TODO: Implement handling for successful invoice payments
            update_payment_status(data, "Completed") # Assuming successful invoice payment maps to Completed status
        else:
            frappe.log_warning(f"Paystack Webhook: Unhandled event type: {event}", "Paystack Webhook Warning")

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
    # Calculate the HMAC SHA512 signature
    hashed = hmac.new(
        secret_key.encode('utf-8'),
        request_body,
        hashlib.sha512
    ).hexdigest()

    # Compare the calculated signature with the received signature
    return hmac.compare_digest(hashed, paystack_signature)


def update_payment_status(data, status):
    """
    Update the payment status in Frappe based on Paystack webhook data.
    """
    # Extract reference details from metadata
    metadata = data.get("metadata")
    if not metadata:
        frappe.log_error("Paystack webhook data missing metadata", "Paystack Webhook Error")
        return

    reference_doctype = metadata.get("reference_doctype")
    reference_docname = metadata.get("reference_docname")
    paystack_reference = data.get("reference") # Paystack transaction reference

    if not reference_doctype or not reference_docname:
        frappe.log_error("Paystack webhook metadata missing reference doctype or docname", "Paystack Webhook Error")
        return

    try:
        doc = frappe.get_doc(reference_doctype, reference_docname)

        # Update document status
        doc.run_method("on_payment_authorized", status) # Call the hook on the document

        # Optionally store Paystack reference on the document
        if hasattr(doc, 'paystack_reference'): # Assuming a field named 'paystack_reference' exists
             doc.paystack_reference = paystack_reference

        doc.save(ignore_permissions=True) # Save the document with updated status
        frappe.db.commit()
        frappe.log_main_tx(f"Paystack Webhook: Payment {status} for {reference_doctype} {reference_docname} (Paystack Ref: {paystack_reference})")

    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Error updating payment status for {reference_doctype} {reference_docname} from Paystack webhook")
        frappe.db.rollback() # Rollback changes in case of error
