# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""
PayFast ITN (Instant Transaction Notification) handler.

This module handles webhook notifications from PayFast payment gateway,
implementing all required security validations per PayFast documentation:
1. IP address validation
2. Signature verification
3. Payment data confirmation

Reference: https://developers.payfast.co.za/docs
"""

import json

import frappe
from frappe import _

# Import PayFast utilities
from payments.payment_gateways.doctype.payfast_settings.payfast_utils import (
    validate_itn_source_ip,
    confirm_payment_with_payfast,
)
from payments.payment_gateways.doctype.payfast_settings.payfast_constants import (
    REQUIRED_ITN_FIELDS,
    VALID_PAYMENT_STATUSES,
)


@frappe.whitelist(allow_guest=True)
def handle_itn():
    """
    ERPNext-compliant ITN (Instant Transaction Notification) handler for PayFast.
    
    Implements all required security validations:
    1. Source IP validation
    2. Required fields validation
    3. Signature verification (in PayfastOrder)
    4. Payment confirmation with PayFast
    
    Returns:
        dict: Response with status message
        
    Reference:
        https://developers.payfast.co.za/docs#notify_page
    """
    try:
        # Get ITN data from form
        itn_data = dict(frappe.request.form)
        
        # Log ITN received for debugging
        frappe.log_error(
            f"PayFast ITN received: {json.dumps(itn_data, indent=2)}",
            "PayFast ITN Received"
        )
        
        # CRITICAL SECURITY: Validate source IP
        source_ip = frappe.request.remote_addr
        is_valid_ip = validate_itn_source_ip()
        
        frappe.log_error(
            f"[ITN DEBUG] IP Validation Check:\n"
            f"Source IP: {source_ip}\n"
            f"Is Valid: {is_valid_ip}\n"
            f"ITN Data: {json.dumps(itn_data, indent=2)}",
            "PayFast ITN IP Validation"
        )
        
        if not is_valid_ip:
            frappe.log_error(
                f"PayFast ITN rejected - invalid source IP: {source_ip}\n"
                f"Expected PayFast IPs (check payfast_utils.py)\n"
                f"Data: {json.dumps(itn_data, indent=2)}",
                "PayFast ITN Security Error"
            )
            frappe.response.http_status_code = 403
            frappe.response["message"] = "Forbidden"
            return
        
        # Validate ITN data structure
        if not validate_itn_data(itn_data):
            frappe.log_error(
                f"PayFast ITN validation failed: {json.dumps(itn_data, indent=2)}",
                "PayFast ITN Validation Error"
            )
            frappe.response.http_status_code = 400
            frappe.response["message"] = "Invalid ITN data"
            return
        
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
    """
    Process ITN notification using PayfastSettings controller.
    
    Args:
        itn_data: Dictionary containing ITN data from PayFast
        
    Returns:
        bool: True if processing succeeded, False otherwise
        
    Raises:
        Exception: Re-raises exceptions for proper error handling
    """
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
        
        # CRITICAL SECURITY: Confirm payment with PayFast
        # This validates the payment was actually processed
        confirmation_result = confirm_payment_with_payfast(itn_data, settings.sandbox_mode)
        
        frappe.log_error(
            f"[ITN DEBUG] Payment Confirmation Check:\n"
            f"Settings: {settings_name}\n"
            f"Sandbox Mode: {settings.sandbox_mode}\n"
            f"Confirmation Result: {confirmation_result}\n"
            f"m_payment_id: {itn_data.get('m_payment_id')}\n"
            f"pf_payment_id: {itn_data.get('pf_payment_id')}\n"
            f"payment_status: {itn_data.get('payment_status')}",
            "PayFast ITN Payment Confirmation"
        )
        
        if not confirmation_result:
            frappe.log_error(
                f"PayFast payment confirmation failed for settings {settings_name}\nData: {json.dumps(itn_data, indent=2)}",
                "PayFast Payment Confirmation Failed"
            )
            return False
        
        # Process the ITN through settings controller
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
    Validate PayFast ITN data structure and required fields.
    
    Args:
        itn_data: Dictionary containing ITN data from PayFast
        
    Returns:
        bool: True if data is valid, False otherwise
        
    Note:
        Signature verification and payment confirmation happen separately
        for better security layering.
    """
    try:
        # Check required fields
        for field in REQUIRED_ITN_FIELDS:
            if not itn_data.get(field):
                frappe.log_error(
                    f"PayFast ITN missing required field: {field}",
                    "PayFast ITN Validation Error"
                )
                return False
        
        # Validate payment status
        payment_status = itn_data.get("payment_status")
        if payment_status not in VALID_PAYMENT_STATUSES:
            frappe.log_error(
                f"PayFast ITN invalid payment status: {payment_status}\nValid statuses: {', '.join(VALID_PAYMENT_STATUSES)}",
                "PayFast ITN Validation Error"
            )
            return False
        
        # Validate amount format
        try:
            amount = float(itn_data.get("amount_gross", 0))
            if amount <= 0:
                frappe.log_error(
                    f"PayFast ITN invalid amount: {amount}",
                    "PayFast ITN Validation Error"
                )
                return False
        except (ValueError, TypeError):
            frappe.log_error(
                f"PayFast ITN invalid amount_gross format: {itn_data.get('amount_gross')}",
                "PayFast ITN Validation Error"
            )
            return False
        
        return True
        
    except Exception as e:
        frappe.log_error(
            f"Error validating PayFast ITN data: {str(e)}\n{frappe.get_traceback()}",
            "PayFast ITN Validation Error"
        )
        return False


def validate_itn(data):
    """
    Legacy validation function - DEPRECATED.
    
    Use validate_itn_data() and payfast_utils.verify_itn_signature() instead
    which follow ERPNext patterns and provide better security.
    
    This function is kept only for backward compatibility and will be removed
    in a future version.
    
    Args:
        data: ITN data dictionary
        
    Returns:
        bool: Always returns False with deprecation warning
    """
    frappe.log_error(
        "validate_itn() called - this function is DEPRECATED!\n"
        "Use validate_itn_data() and payfast_utils.verify_itn_signature() instead.\n"
        "This function will be removed in a future version.",
        "PayFast ITN Deprecated Function Warning"
    )
    return False


# Backward compatibility functions
@frappe.whitelist(allow_guest=True)
def handle_itn_legacy():
    """
    Legacy ITN handler - DEPRECATED.
    
    Use handle_itn() instead which implements all required security validations.
    
    This function is kept only for backward compatibility and will be removed
    in a future version. It redirects to the new handle_itn() function.
    """
    frappe.log_error(
        "handle_itn_legacy() called - this function is DEPRECATED!\n"
        "Use handle_itn() instead which follows ERPNext compliance patterns "
        "and implements all security validations.\n"
        "This function will be removed in a future version.",
        "PayFast ITN Deprecated Function Warning"
    )
    
    # Redirect to new handler
    return handle_itn()
