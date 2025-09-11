# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

import hashlib
import hmac
import json

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def handle_webhook():
	"""
	ERPNext-compliant webhook handler for Yoco notifications.
	This replaces file-based logging with proper frappe.log_error() usage.
	"""
	try:
		# Get webhook data
		request_body = frappe.request.get_data()
		yoco_signature = frappe.request.headers.get("X-Yoco-Signature")
		
		# Get Yoco settings
		settings = frappe.get_single("Yoco Settings")
		webhook_secret = settings.get_password(fieldname="webhook_secret", raise_exception=False)

		# Verify webhook signature
		if not verify_signature(request_body, yoco_signature, webhook_secret):
			frappe.log_error(
				f"Yoco webhook signature verification failed. Signature: {yoco_signature}",
				"Yoco Webhook Signature Error"
			)
			frappe.throw(_("Invalid signature"), frappe.PermissionError)

		# Parse payload
		payload = json.loads(request_body)
		event_type = payload.get("type")
		
		# Log webhook received for debugging
		frappe.log_error(
			f"Yoco webhook received: {event_type}\nPayload: {json.dumps(payload, indent=2)}",
			"Yoco Webhook Received",
			reference_doctype="Yoco Webhook Log"
		)

		# Process webhook using settings controller
		process_webhook_event(event_type, payload)
		
		frappe.response["message"] = "Webhook processed successfully"

	except json.JSONDecodeError as e:
		error_msg = "Yoco webhook payload is not valid JSON"
		frappe.log_error(
			f"{error_msg}: {str(e)}\nPayload: {frappe.request.get_data()}",
			"Yoco Webhook JSON Error"
		)
		frappe.throw(_("Invalid JSON payload"), frappe.ValidationError)
		
	except Exception as e:
		error_msg = f"Error processing Yoco webhook: {str(e)}"
		frappe.log_error(
			f"{error_msg}\n{frappe.get_traceback()}",
			"Yoco Webhook Processing Error"
		)
		frappe.throw(_("Error processing webhook"), frappe.ValidationError)


def process_webhook_event(event_type: str, payload: dict, webhook_log_name: str = None):
	"""Process webhook event using YocoSettings controller"""
	try:
		settings = frappe.get_single("Yoco Settings")
		settings.handle_webhook_event(event_type, payload)
		
	except Exception as e:
		# Log detailed error for debugging
		frappe.log_error(
			f"Failed to process Yoco webhook event {event_type}: {str(e)}\n"
			f"Payload: {json.dumps(payload, indent=2)}\n"
			f"Traceback: {frappe.get_traceback()}",
			"Yoco Webhook Event Processing Error",
			reference_doctype="Yoco Webhook Log",
			reference_name=webhook_log_name
		)
		raise


def handle_charge_succeeded(data):
	"""
	Handle successful charge webhook from Yoco.
	This method is now deprecated - use YocoSettings.handle_charge_succeeded instead
	"""
	frappe.log_error(
		"handle_charge_succeeded called directly - this method is deprecated. "
		"Use YocoSettings.handle_webhook_event instead.",
		"Yoco Webhook Deprecated Method"
	)
	
	try:
		# Get integration request from metadata
		integration_request_id = data.get("metadata", {}).get("integration_request")
		
		if not integration_request_id:
			# Fallback: try to get Payment Request directly
			payment_request_id = data.get("metadata", {}).get("reference_docname")
			if payment_request_id:
				frappe.log_error(
					f"Using fallback Payment Request ID: {payment_request_id}",
					"Yoco Webhook Fallback Processing"
				)
				
				pr = frappe.get_doc("Payment Request", payment_request_id)
				pr.run_method("on_payment_authorized", "Completed")
				frappe.db.commit()
				return
			else:
				frappe.log_error(
					"No integration request or payment request found in webhook metadata",
					"Yoco Webhook Processing Warning"
				)
				return

		# Get Integration Request
		integration_request = frappe.get_doc("Integration Request", integration_request_id)
		request_data = json.loads(integration_request.data)

		frappe.log_error(
			f"Processing Integration Request: {integration_request_id}\n"
			f"Request Data: {json.dumps(request_data, indent=2)}",
			"Yoco Webhook Integration Request Processing"
		)

		# Update Integration Request status
		integration_request.update_status(data, "Completed")

		# Process payment if this is a Payment Request
		if request_data.get("reference_doctype") == "Payment Request":
			payment_request_id = request_data.get("reference_docname")
			
			if payment_request_id:
				pr = frappe.get_doc("Payment Request", payment_request_id)
				
				# Call the payment authorization method
				custom_redirect_to = pr.run_method("on_payment_authorized", "Completed")
				
				frappe.log_error(
					f"Payment Request {payment_request_id} marked as paid",
					"Yoco Payment Processing Success"
				)
				
				frappe.db.commit()
			else:
				frappe.log_error(
					"No Payment Request found in Integration Request data",
					"Yoco Webhook Processing Error"
				)
		else:
			frappe.log_error(
				f"Unexpected reference doctype: {request_data.get('reference_doctype')}",
				"Yoco Webhook Processing Warning"
			)

	except Exception as e:
		frappe.log_error(
			f"Error in handle_charge_succeeded: {str(e)}\n{frappe.get_traceback()}",
			"Yoco Webhook Charge Success Error"
		)
		raise


def handle_charge_failed(data):
	"""
	Handle failed charge webhook from Yoco.
	This method is now deprecated - use YocoSettings.handle_charge_failed instead
	"""
	frappe.log_error(
		"handle_charge_failed called directly - this method is deprecated. "
		"Use YocoSettings.handle_webhook_event instead.",
		"Yoco Webhook Deprecated Method"
	)
	
	try:
		# Get integration request from metadata
		integration_request_id = data.get("metadata", {}).get("integration_request")
		
		if integration_request_id:
			integration_request = frappe.get_doc("Integration Request", integration_request_id)
			integration_request.update_status(data, "Failed")
			
			frappe.log_error(
				f"Integration Request {integration_request_id} marked as failed",
				"Yoco Payment Processing Failed"
			)
			
			frappe.db.commit()

	except Exception as e:
		frappe.log_error(
			f"Error in handle_charge_failed: {str(e)}\n{frappe.get_traceback()}",
			"Yoco Webhook Charge Failed Error"
		)
		raise


def verify_signature(request_body, signature, secret):
	"""Verify the signature of the incoming webhook."""
	if not signature or not secret:
		return False
	
	generated_signature = hmac.new(
		secret.encode('utf-8'),
		request_body,
		hashlib.sha256
	).hexdigest()
	
	return hmac.compare_digest(generated_signature, signature)


# Backward compatibility functions - these are deprecated
def handle_webhook_legacy():
	"""
	Legacy webhook handler - deprecated.
	Use handle_webhook() instead.
	"""
	frappe.log_error(
		"handle_webhook_legacy called - this function is deprecated. "
		"Use handle_webhook() instead.",
		"Yoco Webhook Deprecated Function"
	)
	return handle_webhook()
