# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

import hashlib
import json
from urllib.parse import quote_plus, urlencode

import frappe
from frappe import _
from frappe.integrations.utils import create_request_log
from frappe.model.document import Document
from frappe.utils import call_hook_method, flt, get_url

from payments.utils import create_payment_gateway


class PayfastSettings(Document):
	supported_currencies = ("ZAR",)

	def on_update(self):
		create_payment_gateway(
			"Payfast-" + self.name,
			settings="Payfast Settings",
			controller=self.name,
		)
		call_hook_method("payment_gateway_enabled", gateway="Payfast-" + self.name)

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(
				_(
					"Please select another payment method. Payfast does not support transactions in currency '{0}'"
				).format(currency)
			)

	def validate_minimum_transaction_amount(self, currency, amount):
		minimum_amount = 5.00  # R5.00 as per documentation example
		if flt(amount) < minimum_amount:
			frappe.throw(
				_("For currency {0}, the minimum transaction amount should be {1}").format(
					currency, minimum_amount
				)
			)

	def get_payment_url(self, **kwargs):
		# data to be posted to payfast
		data = {
			"merchant_id": self.merchant_id,
			"merchant_key": self.merchant_key,
			"name_first": kwargs.get("payer_name"),
			"m_payment_id": kwargs.get("order_id"),
			"amount": "{:.2f}".format(flt(kwargs.get("amount"))),
			"item_name": kwargs.get("title"),
			"custom_str1": self.name,
		}
		if self.return_url:
			data["return_url"] = self.return_url
		if self.cancel_url:
			data["cancel_url"] = self.cancel_url
		if self.notify_url:
			data["notify_url"] = self.notify_url
		email = frappe.db.get_value("Customer", kwargs.get("customer"), "email_id")
		if email:
			data["email_address"] = email

		# remove any keys that are not set
		data = {k: v for k, v in data.items() if v}

		# create a signature
		passphrase = self.get_password("passphrase")
		if passphrase:
			data["signature"] = self._get_signature(data, passphrase)

		payfast_url = (
			"https://sandbox.payfast.co.za/eng/process"
			if self.sandbox_mode
			else "https://www.payfast.co.za/eng/process"
		)

		return f"{payfast_url}?{urlencode(data)}"

	def _get_signature(self, data, passphrase):
		# Create URL encoded string
		data = dict(sorted(data.items()))
		pf_output = "&".join(f"{k}={quote_plus(str(v))}" for k, v in data.items())
		if passphrase:
			pf_output += f"&passphrase={passphrase}"
		return hashlib.md5(pf_output.encode("utf-8")).hexdigest()

	def _verify_signature(self, data):
		# Create a hash of the received data
		passphrase = self.get_password("passphrase")
		# remove signature from data
		signature = data.pop("signature")
		signature_to_verify = self._get_signature(data, passphrase)
		return signature == signature_to_verify


@frappe.whitelist(allow_guest=True)
def payfast_itn():
	# ITN callback from payfast
	try:
		frappe.log_error("Payfast ITN called", frappe.local.form_dict)
		# get the posted data from payfast
		data = frappe.local.form_dict

		# get the payment gateway controller
		# custom_str1 should be the name of the payfast settings doc
		controller = frappe.get_doc("Payfast Settings", data.get("custom_str1"))

		# verify the signature
		if not controller._verify_signature(data):
			frappe.log_error("Payfast ITN Signature Verification Failed", data)
			return

		# get the integration request
		integration_request = frappe.get_doc("Integration Request", data.get("m_payment_id"))

		if data.get("payment_status") == "COMPLETE":
			integration_request.db_set("status", "Completed", update_modified=False)
			if integration_request.reference_doctype and integration_request.reference_docname:
				doc = frappe.get_doc(
					integration_request.reference_doctype, integration_request.reference_docname
				)
				doc.run_method("on_payment_authorized", "Completed")

				# redirect to the orders page
				frappe.local.response["type"] = "redirect"
				frappe.local.response["location"] = f"/app/{doc.doctype.lower().replace(' ', '-')}/{doc.name}"
		else:
			integration_request.db_set("status", "Failed", update_modified=False)

	except Exception:
		frappe.log_error(frappe.get_traceback(), "Payfast ITN Error")
