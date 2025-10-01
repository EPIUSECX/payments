# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import time

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
	"customer",
)


def get_context(context):
	"""Get context for PayFast checkout page with diagnostic logging"""
	start_time = time.time()
	frappe.log_error(f"[PAYFAST DEBUG] get_context started at {start_time}", "PayFast Checkout Debug")
	
	context.no_cache = 1

	try:
		step_time = time.time()
		frappe.log_error(f"[PAYFAST DEBUG] Step 1: Validating token {frappe.form_dict.get('token')}", "PayFast Checkout Debug")
		
		validate_integration_request(frappe.form_dict["token"])
		frappe.log_error(f"[PAYFAST DEBUG] Step 1 complete in {time.time() - step_time:.2f}s", "PayFast Checkout Debug")

		step_time = time.time()
		frappe.log_error(f"[PAYFAST DEBUG] Step 2: Getting Integration Request", "PayFast Checkout Debug")
		doc = frappe.get_doc("Integration Request", frappe.form_dict["token"])
		frappe.log_error(f"[PAYFAST DEBUG] Step 2 complete in {time.time() - step_time:.2f}s", "PayFast Checkout Debug")

		step_time = time.time()
		frappe.log_error(f"[PAYFAST DEBUG] Step 3: Parsing payment details", "PayFast Checkout Debug")
		payment_details = json.loads(doc.data)
		frappe.log_error(f"[PAYFAST DEBUG] Step 3 complete in {time.time() - step_time:.2f}s\nDetails: {json.dumps(payment_details, indent=2)}", "PayFast Checkout Debug")

		step_time = time.time()
		frappe.log_error(f"[PAYFAST DEBUG] Step 4: Setting context keys", "PayFast Checkout Debug")
		for key in expected_keys:
			context[key] = payment_details.get(key)
		frappe.log_error(f"[PAYFAST DEBUG] Step 4 complete in {time.time() - step_time:.2f}s", "PayFast Checkout Debug")

		step_time = time.time()
		frappe.log_error(f"[PAYFAST DEBUG] Step 5: Getting Payment Gateway: {payment_details.get('payment_gateway')}", "PayFast Checkout Debug")
		gateway_controller = frappe.get_doc("Payment Gateway", payment_details.get("payment_gateway"))
		frappe.log_error(f"[PAYFAST DEBUG] Step 5 complete in {time.time() - step_time:.2f}s\nController: {gateway_controller.gateway_controller}", "PayFast Checkout Debug")
		
		context.payment_gateway_account = gateway_controller.gateway_controller

		context["token"] = frappe.form_dict["token"]
		context["amount"] = flt(context["amount"])
		
		total_time = time.time() - start_time
		frappe.log_error(f"[PAYFAST DEBUG] get_context completed successfully in {total_time:.2f}s", "PayFast Checkout Debug")

	except Exception as e:
		total_time = time.time() - start_time
		frappe.log_error(
			f"[PAYFAST DEBUG] get_context FAILED after {total_time:.2f}s\nError: {str(e)}\n{frappe.get_traceback()}",
			"PayFast Checkout Error"
		)
		
		frappe.redirect_to_message(
			_("Invalid Token"),
			_("Seems token you are using is invalid!"),
			http_status_code=400,
			indicator_color="red",
		)

		frappe.local.flags.redirect_location = frappe.local.response.location
		raise frappe.Redirect


@frappe.whitelist(allow_guest=True)
def get_payment_url(token):
	"""
	Generate PayFast payment form data for redirect to PayFast portal.
	
	This function is called via AJAX from the checkout page to get the
	PayFast payment form data. It uses the existing Integration Request
	without creating duplicates.
	
	Args:
		token: Integration Request name
		
	Returns:
		dict: PayFast form data including URL, form fields, and order info
	"""
	start_time = time.time()
	frappe.log_error(f"[PAYFAST DEBUG] get_payment_url called with token: {token}", "PayFast get_payment_url Debug")
	
	try:
		step_time = time.time()
		frappe.log_error(f"[PAYFAST DEBUG] Step 1: Getting Integration Request", "PayFast get_payment_url Debug")
		doc = frappe.get_doc("Integration Request", token)
		frappe.log_error(f"[PAYFAST DEBUG] Step 1 complete in {time.time() - step_time:.2f}s", "PayFast get_payment_url Debug")

		step_time = time.time()
		frappe.log_error(f"[PAYFAST DEBUG] Step 2: Parsing payment details", "PayFast get_payment_url Debug")
		payment_details = json.loads(doc.data)
		frappe.log_error(f"[PAYFAST DEBUG] Step 2 complete in {time.time() - step_time:.2f}s\nDetails: {json.dumps(payment_details, indent=2)}", "PayFast get_payment_url Debug")

		step_time = time.time()
		settings_name = payment_details.get("payment_gateway_account")
		frappe.log_error(f"[PAYFAST DEBUG] Step 3: Getting Payfast Settings: {settings_name}", "PayFast get_payment_url Debug")
		controller = frappe.get_doc("Payfast Settings", settings_name)
		frappe.log_error(f"[PAYFAST DEBUG] Step 3 complete in {time.time() - step_time:.2f}s", "PayFast get_payment_url Debug")

		# FIXED: Call create_request() instead of get_payment_url() to avoid creating duplicate Integration Requests
		step_time = time.time()
		frappe.log_error(f"[PAYFAST DEBUG] Step 4: Calling controller.create_request() [FIXED - was get_payment_url]", "PayFast get_payment_url Debug")
		payment_data = controller.create_request(payment_details)
		frappe.log_error(f"[PAYFAST DEBUG] Step 4 complete in {time.time() - step_time:.2f}s\nData keys: {list(payment_data.keys())}", "PayFast get_payment_url Debug")

		total_time = time.time() - start_time
		frappe.log_error(f"[PAYFAST DEBUG] get_payment_url completed in {total_time:.2f}s", "PayFast get_payment_url Debug")
		
		return payment_data
		
	except Exception as e:
		total_time = time.time() - start_time
		frappe.log_error(
			f"[PAYFAST DEBUG] get_payment_url FAILED after {total_time:.2f}s\nError: {str(e)}\n{frappe.get_traceback()}",
			"PayFast get_payment_url Error"
		)
		raise
