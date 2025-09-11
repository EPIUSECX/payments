# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

import hashlib
import json

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def handle_itn():
    """
    ERPNext-compliant ITN (Instant Transaction Notification) handler for PayFast.
    This follows the same patterns as the Yoco webhook handler.
    """
    try:
        # Get ITN data from form
        itn_data = dict(frappe.request.form)
        
        # Log ITN received for debugging
        frappe.log_error(
            f"PayFast ITN received: {json.dumps(itn_data, indent=2)}",
            "PayFast ITN Received"
        )
        
        # Validate ITN data
        if not validate_itn_data(itn_data):
            frappe.log_error(
                f"PayFast ITN validation failed: {json.dumps(itn_data, indent=2)}",
                "PayFast ITN Validation Error"
            )
            frappe.throw(_("Invalid ITN data"), frappe.ValidationError)

        # Process ITN using PayfastSettings controller
        process_itn_notification(itn_data)
        
        frappe.response["message"] = "OK"

    except Exception as e:
        error_msg = f"Error processing PayFast ITN: {str(e)}"
        frappe.log_error(
            f"{error_msg}\n{frappe.get_traceback()}\nITN Data: {json.dumps(dict(frappe.request.form), indent=2)}",
            "PayFast ITN Processing Error"
        )
        frappe.response.http_status_code = 500
        frappe.response["message"] = "Error processing ITN"


def process_itn_notification(itn_data: dict):
    """Process ITN notification using PayfastSettings controller"""
    try:
        # Get PayFast settings from custom_str1
        settings_name = itn_data.get("custom_str1")
        if not settings_name:
            frappe.log_error(
                "PayFast ITN missing custom_str1 (settings reference)",
                "PayFast ITN Processing Error"
            )
            return False
            
        settings = frappe.get_doc("Payfast Settings", settings_name)
        success = settings.handle_itn_notification(itn_data)
        
        if success:
            frappe.log_error(
                f"PayFast ITN processed successfully for settings {settings_name}",
                "PayFast ITN Processing Success"
            )
        
        return success
        
    except Exception as e:
        frappe.log_error(
            f"Failed to process PayFast ITN notification: {str(e)}\n{frappe.get_traceback()}",
            "PayFast ITN Processing Error"
        )
        raise


def validate_itn_data(itn_data: dict) -> bool:
    """
    Basic validation of PayFast ITN data.
    More comprehensive validation happens in PayfastOrder.verify_itn_signature()
    """
    try:
        # Check required fields
        required_fields = ["m_payment_id", "payment_status", "amount_gross"]
        for field in required_fields:
            if not itn_data.get(field):
                frappe.log_error(
                    f"PayFast ITN missing required field: {field}",
                    "PayFast ITN Validation Error"
                )
                return False
        
        # Validate payment status
        valid_statuses = ["COMPLETE", "FAILED", "CANCELLED"]
        payment_status = itn_data.get("payment_status")
        if payment_status not in valid_statuses:
            frappe.log_error(
                f"PayFast ITN invalid payment status: {payment_status}",
                "PayFast ITN Validation Error"
            )
            return False
        
        # Validate amount format
        try:
            float(itn_data.get("amount_gross", 0))
        except ValueError:
            frappe.log_error(
                f"PayFast ITN invalid amount_gross format: {itn_data.get('amount_gross')}",
                "PayFast ITN Validation Error"
            )
            return False
        
        return True
        
    except Exception as e:
        frappe.log_error(
            f"Error validating PayFast ITN data: {str(e)}",
            "PayFast ITN Validation Error"
        )
        return False


def validate_itn(data):
    """
    Legacy validation function - deprecated.
    Use validate_itn_data() instead which follows ERPNext patterns.
    """
    frappe.log_error(
        "validate_itn called - this function is deprecated. "
        "Use validate_itn_data() instead which follows ERPNext patterns.",
        "PayFast ITN Deprecated Function"
    )
    
    try:
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
            frappe.log_error(
                f"PayFast ITN signature mismatch. Received: {received_signature}, Generated: {generated_signature}", 
                "PayFast ITN Validation Error"
            )
            return False
            
        return True
        
    except Exception as e:
        frappe.log_error(
            f"Legacy PayFast ITN validation error: {str(e)}",
            "PayFast ITN Legacy Validation Error"
        )
        return False


# Backward compatibility functions
@frappe.whitelist(allow_guest=True) 
def handle_itn_legacy():
    """
    Legacy ITN handler - deprecated.
    Use handle_itn() instead.
    """
    frappe.log_error(
        "handle_itn_legacy called - this function is deprecated. "
        "Use handle_itn() instead which follows ERPNext compliance patterns.",
        "PayFast ITN Deprecated Function"
    )
    
    try:
        itn_data = dict(frappe.request.form)
        
        if not validate_itn_data(itn_data):
            frappe.log_error("PayFast ITN validation failed", "PayFast ITN Error")
            return

        if itn_data.get("payment_status") == "COMPLETE":
            payment_request_id = itn_data.get("custom_str2")
            if payment_request_id:
                pr = frappe.get_doc("Payment Request", payment_request_id)
                pr.run_method("set_as_paid")
        else:
            # Log other statuses for now
            frappe.log_error(
                f"PayFast ITN: Received non-complete status '{itn_data.get('payment_status')}'", 
                "PayFast ITN Info"
            )

        frappe.response["message"] = "OK"

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Error processing PayFast ITN")
        frappe.response.http_status_code = 500
