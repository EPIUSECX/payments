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
	return frappe.db.get_value("Paystack Settings", payment_gateway_account, "public_key")


@frappe.whitelist(allow_guest=True)
def make_payment(paystack_txn_ref, data, reference_doctype, reference_docname, payment_gateway_account):
	data = json.loads(data)
	data.update({
		"paystack_txn_ref": paystack_txn_ref,
		"reference_doctype": reference_doctype,
		"reference_docname": reference_docname
	})

	controller = frappe.get_doc("Paystack Settings", payment_gateway_account)
	return controller.create_request(data)