# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe import _
from frappe.utils import flt

from payments.utils.utils import validate_integration_request

no_cache = 1

expected_keys = (
	"amount",
	"title",
	"description",
	"reference_doctype",
	"reference_docname",
	"payer_name",
	"payer_email",
	"order_id",
	"currency",
)


def get_context(context):
	context.no_cache = 1

	try:
		validate_integration_request(frappe.form_dict["token"])

		doc = frappe.get_doc("Integration Request", frappe.form_dict["token"])

		payment_details = json.loads(doc.data)

		for key in expected_keys:
			context[key] = payment_details[key]

		gateway_controller = frappe.get_doc("Payment Gateway", payment_details.get("payment_gateway"))
		context.payment_gateway_account = gateway_controller.gateway_controller
		context.api_key = get_api_key(context.payment_gateway_account)
		
		# Get Apple Pay configuration
		apple_pay_config = get_apple_pay_config(context.payment_gateway_account)
		context.enable_apple_pay = apple_pay_config["enable_apple_pay"]
		context.apple_pay_merchant_id = apple_pay_config["apple_pay_merchant_id"]

		context["token"] = frappe.form_dict["token"]
		context["amount"] = flt(context["amount"])

	except Exception:
		frappe.redirect_to_message(
			_("Invalid Token"),
			_("Seems token you are using is invalid!"),
			http_status_code=400,
			indicator_color="red",
		)

		frappe.local.flags.redirect_location = frappe.local.response.location
		raise frappe.Redirect


def get_api_key(payment_gateway_account):
	return frappe.db.get_value("Yoco Settings", payment_gateway_account, "public_key")


def get_apple_pay_config(payment_gateway_account):
	"""Get Apple Pay configuration from Yoco Settings."""
	settings = frappe.get_doc("Yoco Settings", payment_gateway_account)
	return {
		"enable_apple_pay": settings.get("enable_apple_pay", 1),
		"apple_pay_merchant_id": settings.get("apple_pay_merchant_id", "")
	}


@frappe.whitelist(allow_guest=True)
def make_payment(yoco_token, data, reference_doctype, reference_docname, payment_gateway_account):
	"""
	ERPNext-compliant payment processing via YocoSettings controller.
	This method now delegates to the controller instead of processing directly.
	"""
	try:
		# Parse and validate data
		data = json.loads(data) if isinstance(data, str) else data
		token = data.get("token")
		
		if not token:
			frappe.throw(_("Integration Request token missing"))

		# Get Integration Request
		integration_request = frappe.get_doc("Integration Request", token)
		
		# Get YocoSettings controller
		yoco_settings = frappe.get_doc("Yoco Settings", payment_gateway_account)
		
		# Delegate payment processing to controller
		payment_data = {
			"yoco_token_id": yoco_token,
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
			"token": token,
			"payment_details": data
		}
		
		# Process payment via controller
		result = yoco_settings.process_payment_completion(payment_data, integration_request)
		
		return result
		
	except Exception as e:
		frappe.log_error(
			f"Yoco payment processing error: {str(e)}\n{frappe.get_traceback()}",
			"Yoco Payment Processing Error"
		)
		return {
			"redirect_to": "payment-failed",
			"status": "Failed",
			"error": str(e)
		}


# Backward compatibility - deprecated method
@frappe.whitelist(allow_guest=True)
def make_payment_legacy(yoco_token, data, reference_doctype, reference_docname, payment_gateway_account):
	"""
	Legacy payment processing method - deprecated.
	Kept for backward compatibility but logs deprecation warning.
	"""
	frappe.log_error(
		"make_payment_legacy called - this method is deprecated. "
		"Use make_payment() instead which delegates to YocoSettings controller.",
		"Yoco Payment Deprecated Method"
	)
	
	try:
		data = json.loads(data)
		data.update({
			"yoco_token_id": yoco_token,
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname
		})

		# Get the Integration Request from the token
		token = data.get("token")
		if not token:
			frappe.throw(_("Integration Request token missing"))

		# Get Integration Request and update it
		integration_request = frappe.get_doc("Integration Request", token)
		integration_request.db_set("status", "Completed", update_modified=False)
		
		# Process the payment in ERPNext
		if reference_doctype == "Payment Request" and reference_docname:
			payment_request = frappe.get_doc("Payment Request", reference_docname)
			
			# Call the payment authorization method to create Payment Entry, Sales Invoice, etc.
			custom_redirect_to = payment_request.run_method("on_payment_authorized", "Completed")
			
			frappe.db.commit()
			
			# Return success redirect
			redirect_url = f"payment-success?doctype={reference_doctype}&docname={reference_docname}"
			
			if custom_redirect_to:
				redirect_url = custom_redirect_to
			
			return {
				"redirect_to": redirect_url,
				"status": "Completed"
			}
		else:
			frappe.throw(_("Invalid payment reference"))
		
	except Exception as e:
		frappe.log_error(
			f"Legacy Yoco payment processing error: {str(e)}\n{frappe.get_traceback()}",
			"Yoco Payment Legacy Processing Error"
		)
		return {
			"redirect_to": "payment-failed",
			"status": "Failed"
		}
