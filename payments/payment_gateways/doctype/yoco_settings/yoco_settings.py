# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.integrations.utils import create_request_log
from frappe.model.document import Document
from frappe.utils import call_hook_method, flt, get_url

from payments.utils import create_payment_gateway


class YocoSettings(Document):
	supported_currencies = ("ZAR",)

	def on_update(self):
		create_payment_gateway(
			"Yoco-" + self.name,
			settings="Yoco Settings",
			controller=self.name,
		)
		call_hook_method("payment_gateway_enabled", gateway="Yoco-" + self.name)

	@frappe.whitelist()
	def test_connection(self):
		"""Test the connection to the Yoco API."""
		import requests

		secret_key = self.get_password(fieldname="secret_key", raise_exception=False)
		if not secret_key:
			return {"status": "error", "message": "Please set the Secret Key."}

		# Use the correct Yoco API endpoint for testing credentials
		test_url = "https://payments.yoco.com/api/webhooks"

		headers = {
			"Authorization": f"Bearer {secret_key}",
			"Content-Type": "application/json"
		}

		try:
			response = requests.get(test_url, headers=headers, timeout=10)
			response.raise_for_status()

			return {"status": "success", "message": "Connection successful!"}

		except requests.exceptions.RequestException as e:
			return {"status": "error", "message": f"Connection failed: {e}"}
		except Exception as e:
			return {"status": "error", "message": f"An unexpected error occurred: {e}"}

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(
				_(
					"Please select another payment method. Yoco does not support transactions in currency '{0}'"
				).format(currency)
			)

	def validate_minimum_transaction_amount(self, currency, amount):
		# Minimum transaction amount is R1.00 (100 cents)
		minimum_amount = 1.00

		if flt(amount) < minimum_amount:
			frappe.throw(
				_("For currency {0}, the minimum transaction amount should be {1}").format(
					currency, minimum_amount
				)
			)

	def get_payment_url(self, **kwargs):
		integration_request = create_request_log(kwargs, service_name="Yoco")
		return get_url(f"./yoco_checkout?token={integration_request.name}")

	def create_request(self, data):
		"""
		For Yoco, the payment is processed entirely on the frontend with the Yoco SDK.
		The webhook handles the completion and ERPNext integration.
		This method just creates the Integration Request for tracking.
		"""
		self.data = frappe._dict(data)

		try:
			self.integration_request = create_request_log(self.data, service_name="Yoco")
			return self.finalize_request()

		except Exception:
			frappe.log_error(frappe.get_traceback())
			return {
				"redirect_to": frappe.redirect_to_message(
					_("Server Error"),
					_(
						"It seems that there is an issue with the server's Yoco configuration. In case of failure, the amount will get refunded to your account."
					),
				),
				"status": 401,
			}

	def finalize_request(self):
		redirect_to = self.data.get("redirect_to") or None
		redirect_message = self.data.get("redirect_message") or None
		status = self.integration_request.status

		if self.flags.status_changed_to == "Completed":
			if self.data.reference_doctype and self.data.reference_docname:
				custom_redirect_to = None
				try:
					custom_redirect_to = frappe.get_doc(
						self.data.reference_doctype, self.data.reference_docname
					).run_method("on_payment_authorized", self.flags.status_changed_to)
				except Exception:
					frappe.log_error(frappe.get_traceback())

				if custom_redirect_to:
					redirect_to = custom_redirect_to

				redirect_url = f"payment-success?doctype={self.data.reference_doctype}&docname={self.data.reference_docname}"
		else:
			redirect_url = "payment-failed"

		if redirect_to and "?" in redirect_url:
			redirect_url += "&" + urlencode({"redirect_to": redirect_to})
		elif redirect_to:
			redirect_url += "?" + urlencode({"redirect_to": redirect_to})

		if redirect_message:
			redirect_url += "&" + urlencode({"redirect_message": redirect_message})

		return {"redirect_to": redirect_url, "status": status}
