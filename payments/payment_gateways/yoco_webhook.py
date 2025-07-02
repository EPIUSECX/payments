# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

import hashlib
import hmac
import json
import os

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def handle_webhook():
	"""
	Handle webhook notifications from Yoco.
	This is the single entry point for all Yoco webhooks.
	"""
	log_path = os.path.join(frappe.utils.get_bench_path(), "logs", "yoco_webhook.log")
	
	# Log the incoming webhook for debugging
	with open(log_path, "a") as f:
		f.write(f"--- New Yoco Webhook Request ---\n")
		f.write(f"Headers: {frappe.request.headers}\n")
		f.write(f"Body: {frappe.request.data}\n")

	request_body = frappe.request.data
	yoco_signature = frappe.request.headers.get("X-Yoco-Signature")
	
	# Get Yoco settings - assuming there's only one Yoco Settings doc
	settings = frappe.get_doc("Yoco Settings")
	webhook_secret = settings.get_password(fieldname="webhook_secret", raise_exception=False)

	# Verify webhook signature
	if not verify_signature(request_body, yoco_signature, webhook_secret):
		with open(log_path, "a") as f:
			f.write("Signature verification failed.\n")
		frappe.log_error("Yoco webhook signature verification failed", "Yoco Webhook Error")
		frappe.throw(_("Invalid signature"), frappe.PermissionError)

	try:
		payload = json.loads(request_body)
		event_type = payload.get("type")
		data = payload.get("data", {}).get("object", {})

		with open(log_path, "a") as f:
			f.write(f"Payload: {json.dumps(payload, indent=4)}\n")

		if event_type == "charge.succeeded":
			handle_charge_succeeded(data, log_path)
		elif event_type == "charge.failed":
			handle_charge_failed(data, log_path)
		else:
			# Log other events for future handling
			frappe.log_error(
				f"Yoco Webhook: Received unhandled event type '{event_type}'", 
				"Yoco Webhook Info"
			)

		frappe.response["message"] = "Webhook received successfully"

	except json.JSONDecodeError:
		with open(log_path, "a") as f:
			f.write("Error: Invalid JSON payload.\n")
		frappe.log_error("Yoco webhook payload is not valid JSON", "Yoco Webhook Error")
		frappe.throw(_("Invalid JSON payload"), frappe.ValidationError)
	except Exception as e:
		with open(log_path, "a") as f:
			f.write(f"Error processing webhook: {e}\n")
			f.write(frappe.get_traceback())
		frappe.log_error(frappe.get_traceback(), "Error processing Yoco webhook")
		frappe.throw(_("Error processing webhook"), frappe.ValidationError)


def handle_charge_succeeded(data, log_path):
	"""Handle successful charge webhook from Yoco."""
	try:
		# Get integration request from metadata
		integration_request_id = data.get("metadata", {}).get("integration_request")
		
		if not integration_request_id:
			# Fallback: try to get Payment Request directly
			payment_request_id = data.get("metadata", {}).get("reference_docname")
			if payment_request_id:
				with open(log_path, "a") as f:
					f.write(f"Using fallback Payment Request ID: {payment_request_id}\n")
				
				pr = frappe.get_doc("Payment Request", payment_request_id)
				pr.run_method("on_payment_authorized", "Completed")
				frappe.db.commit()
				return
			else:
				frappe.log_error("No integration request or payment request found in webhook metadata", "Yoco Webhook Error")
				return

		# Get Integration Request
		integration_request = frappe.get_doc("Integration Request", integration_request_id)
		request_data = json.loads(integration_request.data)

		with open(log_path, "a") as f:
			f.write(f"Processing Integration Request: {integration_request_id}\n")
			f.write(f"Request Data: {request_data}\n")

		# Update Integration Request status
		integration_request.update_status(data, "Completed")

		# Process payment if this is a Payment Request
		if request_data.get("reference_doctype") == "Payment Request":
			payment_request_id = request_data.get("reference_docname")
			
			if payment_request_id:
				pr = frappe.get_doc("Payment Request", payment_request_id)
				
				# Call the payment authorization method
				custom_redirect_to = pr.run_method("on_payment_authorized", "Completed")
				
				with open(log_path, "a") as f:
					f.write(f"Payment Request {payment_request_id} marked as paid\n")
				
				frappe.db.commit()
			else:
				frappe.log_error("No Payment Request found in Integration Request data", "Yoco Webhook Error")
		else:
			frappe.log_error(f"Unexpected reference doctype: {request_data.get('reference_doctype')}", "Yoco Webhook Error")

	except Exception as e:
		with open(log_path, "a") as f:
			f.write(f"Error in handle_charge_succeeded: {e}\n")
			f.write(frappe.get_traceback())
		frappe.log_error(frappe.get_traceback(), "Error processing successful Yoco charge")


def handle_charge_failed(data, log_path):
	"""Handle failed charge webhook from Yoco."""
	try:
		# Get integration request from metadata
		integration_request_id = data.get("metadata", {}).get("integration_request")
		
		if integration_request_id:
			integration_request = frappe.get_doc("Integration Request", integration_request_id)
			integration_request.update_status(data, "Failed")
			
			with open(log_path, "a") as f:
				f.write(f"Integration Request {integration_request_id} marked as failed\n")
			
			frappe.db.commit()

	except Exception as e:
		with open(log_path, "a") as f:
			f.write(f"Error in handle_charge_failed: {e}\n")
		frappe.log_error(frappe.get_traceback(), "Error processing failed Yoco charge")


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
