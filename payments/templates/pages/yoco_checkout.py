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


@frappe.whitelist(allow_guest=True)
def make_payment(yoco_token, data, reference_doctype, reference_docname, payment_gateway_account):
	"""Process Yoco payment after user completes checkout."""
	try:
		data = json.loads(data)
		data.update({
			"yoco_token_id": yoco_token,
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname
		})

		controller = frappe.get_doc("Yoco Settings", payment_gateway_account)
		
		# Set the data and integration request from the token
		controller.data = frappe._dict(data)
		
		# Get the integration request from the token
		token = data.get("token")
		if token:
			controller.integration_request = frappe.get_doc("Integration Request", token)
		else:
			frappe.throw(_("Integration Request token missing"))
		
		# Process the charge with Yoco API
		result = controller.create_charge_on_yoco()
		
		# Ensure we return a proper response
		if not result:
			return {
				"redirect_to": "payment-failed",
				"status": "Failed"
			}
		
		return result
		
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Yoco Payment Processing Error")
		return {
			"redirect_to": "payment-failed",
			"status": "Failed"
		}
