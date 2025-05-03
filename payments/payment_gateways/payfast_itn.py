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
    data = frappe.request.form # Get POST data from Payfast

    # TODO: Implement ITN validation steps:
    # 1. Signature Verification
    # 2. Source IP Verification
    # 3. Data Integrity Check

    if validate_itn(data):
        # TODO: Update payment status in Frappe based on ITN data
        update_payment_status(data)
        frappe.response["message"] = "OK" # Respond with "OK" to Payfast
    else:
        frappe.response["message"] = "Error: ITN validation failed"
        frappe.log_error("Payfast ITN validation failed", "Payfast ITN Error")

def validate_itn(data):
    """
    Validate the ITN data received from Payfast.
    """
    settings = frappe.get_doc("Payfast Settings")
    received_signature = data.get("signature")

    # 1. Signature Verification
    # Sort the data by key and concatenate values with passphrase
    sorted_data = sorted([(key, value) for key, value in data.items() if key != "signature"])
    data_string = ""
    for key, value in sorted_data:
        data_string += str(value) + "&"

    # Add passphrase to the end
    data_string += settings.get_password(fieldname="passphrase", raise_exception=False)

    # Calculate MD5 hash
    generated_signature = hashlib.md5(data_string.encode('utf-8')).hexdigest()

    if generated_signature != received_signature:
        frappe.log_error(f"Payfast ITN signature mismatch. Received: {received_signature}, Generated: {generated_signature}", "Payfast ITN Validation Error")
        return False

    # 2. Source IP Verification
    # Payfast ITN IP addresses (including sandbox IP)
    payfast_ips = [
        "197.97.145.144", "197.97.145.145", "197.97.145.146", "197.97.145.147",
        "197.97.145.148", "197.97.145.149", "197.97.145.150", "197.97.145.151",
        "197.97.145.152", "197.97.145.153", "197.97.145.154", "197.97.145.155",
        "197.97.145.156", "197.97.145.157", "197.97.145.158", "197.97.145.159",
        "41.74.179.192", "41.74.179.193", "41.74.179.194", "41.74.179.195",
        "41.74.179.196", "41.74.179.197", "41.74.179.198", "41.74.179.199",
        "41.74.179.200", "41.74.179.201", "41.74.179.202", "41.74.179.203",
        "41.74.179.204", "41.74.179.205", "41.74.179.206", "41.74.179.207",
        "41.74.179.208", "41.74.179.209", "41.74.179.210", "41.74.179.211",
        "41.74.179.212", "41.74.179.213", "41.74.179.214", "41.74.179.215",
        "41.74.179.216", "41.74.179.217", "41.74.179.218", "41.74.179.219",
        "41.74.179.220", "41.74.179.221", "41.74.179.222", "41.74.179.223",
        "102.216.36.0", "102.216.36.1", "102.216.36.2", "102.216.36.3",
        "102.216.36.4", "102.216.36.5", "102.216.36.6", "102.216.36.7",
        "102.216.36.8", "102.216.36.9", "102.216.36.10", "102.216.36.11",
        "102.216.36.12", "102.216.36.13", "102.216.36.14", "102.216.36.15",
        "102.216.36.128", "102.216.36.129", "102.216.36.130", "102.216.36.131",
        "102.216.36.132", "102.216.36.133", "102.216.36.134", "102.216.36.135",
        "102.216.36.136", "102.216.36.137", "102.216.36.138", "102.216.36.139",
        "102.216.36.140", "102.216.36.141", "102.216.36.142", "102.216.36.143",
        "144.126.193.139" # Sandbox IP
    ]

    if frappe.request.remote_addr not in payfast_ips:
        frappe.log_error(f"Payfast ITN received from invalid IP: {frappe.request.remote_addr}", "Payfast ITN Validation Error")
        return False

    # 3. Data Integrity Check
    reference_doctype = data.get("custom_str1")
    reference_docname = data.get("custom_str2")
    amount_gross = data.get("amount_gross")
    item_name = data.get("item_name")
    item_description = data.get("item_description")

    if not reference_doctype or not reference_docname:
        frappe.log_error("Payfast ITN missing reference doctype or docname for data integrity check", "Payfast ITN Validation Error")
        return False

    try:
        original_doc = frappe.get_doc(reference_doctype, reference_docname)

        # Compare critical fields (adjust field names based on your document structure)
        # Assuming the document has fields like 'grand_total', 'item_name', 'description'
        if flt(amount_gross) != flt(original_doc.grand_total): # Example field name
            frappe.log_error(f"Payfast ITN amount mismatch. Received: {amount_gross}, Original: {original_doc.grand_total}", "Payfast ITN Validation Error")
            return False

        if item_name and item_name != original_doc.item_name: # Example field name
             frappe.log_error(f"Payfast ITN item name mismatch. Received: {item_name}, Original: {original_doc.item_name}", "Payfast ITN Validation Error")
             return False

        if item_description and item_description != original_doc.description: # Example field name
             frappe.log_error(f"Payfast ITN item description mismatch. Received: {item_description}, Original: {original_doc.description}", "Payfast ITN Validation Error")
             return False

        # Add more data integrity checks as needed based on your document and Payfast data

    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Error during Payfast ITN data integrity check for {reference_doctype} {reference_docname}")
        return False

    return True


    return True

def update_payment_status(data):
    """
    Update the payment status in Frappe based on validated ITN data.
    """
    # Extract reference doctype and docname from ITN data
    reference_doctype = data.get("custom_str1")
    reference_docname = data.get("custom_str2")
    payfast_status = data.get("payment_status") # Get status from Payfast data
    pf_payment_id = data.get("pf_payment_id") # Get Payfast Payment ID

    if not reference_doctype or not reference_docname:
        frappe.log_error("Payfast ITN missing reference doctype or docname", "Payfast ITN Error")
        return

    try:
        doc = frappe.get_doc(reference_doctype, reference_docname)

        # Map Payfast statuses to Frappe payment statuses and update document
        if payfast_status == "COMPLETE":
            doc.run_method("on_payment_authorized", "Completed")
            frappe.log_main_tx(f"Payfast ITN: Payment {payfast_status} for {reference_doctype} {reference_docname} (Payfast ID: {pf_payment_id})")
        elif payfast_status == "PENDING":
            doc.run_method("on_payment_authorized", "Pending") # Assuming "Pending" status exists in Frappe
            frappe.log_main_tx(f"Payfast ITN: Payment {payfast_status} for {reference_doctype} {reference_docname} (Payfast ID: {pf_payment_id})")
        elif payfast_status == "CANCELLED":
            doc.run_method("on_payment_authorized", "Cancelled") # Assuming "Cancelled" status exists in Frappe
            frappe.log_main_tx(f"Payfast ITN: Payment {payfast_status} for {reference_doctype} {reference_docname} (Payfast ID: {pf_payment_id})")
        elif payfast_status == "EXPIRED":
            doc.run_method("on_payment_authorized", "Expired") # Assuming "Expired" status exists in Frappe
            frappe.log_main_tx(f"Payfast ITN: Payment {payfast_status} for {reference_doctype} {reference_docname} (Payfast ID: {pf_payment_id})")
        elif payfast_status == "FAILED":
            doc.run_method("on_payment_authorized", "Failed")
            frappe.log_main_tx(f"Payfast ITN: Payment {payfast_status} for {reference_doctype} {reference_docname} (Payfast ID: {pf_payment_id})")
        else:
            frappe.log_warning(f"Payfast ITN: Unhandled payment status {payfast_status} for {reference_doctype} {reference_docname} (Payfast ID: {pf_payment_id})", "Payfast ITN Warning")

        # Optionally store the Payfast Payment ID on the document
        if hasattr(doc, 'payfast_payment_id'): # Assuming a field named 'payfast_payment_id' exists
             doc.payfast_payment_id = pf_payment_id

        doc.save(ignore_permissions=True) # Save the document with updated status
        frappe.db.commit()


    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Error updating payment status for {reference_doctype} {reference_docname}")
        frappe.db.rollback() # Rollback changes in case of error
