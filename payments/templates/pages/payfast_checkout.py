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
@frappe.whitelist(allow_guest=True)
def get_payment_url(token):
	doc = frappe.get_doc("Integration Request", token)
	payment_details = json.loads(doc.data)
	
	controller = frappe.get_doc("Payfast Settings", "Payfast")
	payment_url = controller.get_payment_url(**payment_details)

	return payment_url