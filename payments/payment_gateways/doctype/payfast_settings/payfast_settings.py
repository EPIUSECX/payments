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
		"""ERPNext compliant payment gateway registration"""
		create_payment_gateway(
			"Payfast-" + self.name,
			settings="Payfast Settings",
			controller=self.name,
		)
		call_hook_method("payment_gateway_enabled", gateway="Payfast-" + self.name)

	def validate(self):
		"""Validate PayFast settings"""
		if not self.flags.ignore_mandatory:
			self.validate_payfast_credentials()

	def validate_payfast_credentials(self):
		"""Validate PayFast merchant credentials"""
		if not self.merchant_id:
			frappe.throw(_("Merchant ID is required"))
		if not self.merchant_key:
			frappe.throw(_("Merchant Key is required"))

	def validate_transaction_currency(self, currency):
		"""Validate currency is supported"""
		if currency not in self.supported_currencies:
			frappe.throw(
				_(
					"Please select another payment method. Payfast does not support transactions in currency '{0}'"
				).format(currency)
			)

	def validate_minimum_transaction_amount(self, currency, amount):
		"""Validate minimum transaction amount"""
		minimum_amount = 5.00  # R5.00 as per PayFast documentation
		if flt(amount) < minimum_amount:
			frappe.throw(
				_("For currency {0}, the minimum transaction amount should be {1}").format(
					currency, minimum_amount
				)
			)

	def get_payment_url(self, **kwargs):
		"""Get PayFast payment URL using Integration Request pattern"""
		integration_request = create_request_log(kwargs, service_name="PayFast")
		return get_url(f"./payfast_checkout?token={integration_request.name}")

	def create_request(self, data):
		"""
		ERPNext-compliant request creation using Integration Request pattern
		"""
		self.data = frappe._dict(data)

		try:
			# Create Integration Request for tracking
			self.integration_request = create_request_log(self.data, service_name="PayFast")
			
			# Create PayFast Order for transaction tracking
			payfast_order_data = self.create_payfast_order()
			
			# Generate PayFast payment form data
			return self.generate_payment_form(payfast_order_data)

		except Exception as e:
			frappe.log_error(
				f"PayFast request creation failed: {str(e)}\n{frappe.get_traceback()}",
				"PayFast Request Creation Error"
			)
			return {
				"redirect_to": frappe.redirect_to_message(
					_("Server Error"),
					_(
						"There is an issue with the server's PayFast configuration. Please try again later."
					),
				),
				"status": 401,
			}

	def create_payfast_order(self):
		"""Create PayFastOrder record for transaction tracking"""
		from payments.payment_gateways.doctype.payfast_order.payfast_order import PayfastOrder
		
		order_data = PayfastOrder.create_order(
			m_payment_id=self.integration_request.name,
			amount_gross=self.data.amount,
			currency=self.data.currency or "ZAR",
			item_name=self.data.title,
			meta_data={
				"integration_request": self.integration_request.name,
				"reference_doctype": self.data.reference_doctype,
				"reference_docname": self.data.reference_docname,
				"description": self.data.description
			},
			ref_dt=self.data.reference_doctype,
			ref_dn=self.data.reference_docname
		)
		
		return order_data

	def generate_payment_form(self, payfast_order_data):
		"""Generate PayFast payment form data"""
		# Prepare data for PayFast form
		form_data = {
			"merchant_id": self.merchant_id,
			"merchant_key": self.merchant_key,
			"name_first": self.data.get("payer_name", "").split(" ")[0] if self.data.get("payer_name") else "",
			"name_last": " ".join(self.data.get("payer_name", "").split(" ")[1:]) if self.data.get("payer_name") else "",
			"m_payment_id": payfast_order_data["m_payment_id"],
			"amount": "{:.2f}".format(flt(self.data.amount)),
			"item_name": self.data.get("title", "Payment"),
			"item_description": self.data.get("description", ""),
			"custom_str1": self.name,  # PayFast Settings document name
			"custom_str2": self.data.reference_docname,  # Reference document name
		}

		# Add optional fields
		if self.return_url:
			form_data["return_url"] = self.return_url
		if self.cancel_url:
			form_data["cancel_url"] = self.cancel_url
		if self.notify_url:
			form_data["notify_url"] = self.notify_url
		
		# Add email if available
		email = self.data.get("payer_email")
		if not email and self.data.get("customer"):
			email = frappe.db.get_value("Customer", self.data.customer, "email_id")
		if email:
			form_data["email_address"] = email

		# Remove any empty values
		form_data = {k: v for k, v in form_data.items() if v}

		# Create signature
		passphrase = self.get_password("passphrase", raise_exception=False)
		if passphrase:
			form_data["signature"] = self._get_signature(form_data, passphrase)

		# Generate PayFast URL
		payfast_url = (
			"https://sandbox.payfast.co.za/eng/process"
			if self.sandbox_mode
			else "https://www.payfast.co.za/eng/process"
		)

		return {
			"payfast_url": payfast_url,
			"form_data": form_data,
			"payfast_order": payfast_order_data["payfast_order"]
		}

	def handle_itn_notification(self, itn_data: dict):
		"""
		Handle ITN (Instant Transaction Notification) from PayFast
		ERPNext-compliant ITN processing with proper logging and order tracking
		"""
		from payments.payment_gateways.doctype.payfast_order.payfast_order import PayfastOrder
		
		try:
			# Log ITN received
			frappe.log_error(
				f"PayFast ITN received: {json.dumps(itn_data, indent=2)}",
				"PayFast ITN Received"
			)
			
			# Find PayFast Order by m_payment_id
			m_payment_id = itn_data.get("m_payment_id")
			if not m_payment_id:
				frappe.log_error("PayFast ITN missing m_payment_id", "PayFast ITN Error")
				return False
			
			payfast_order = frappe.db.get_value("PayFast Order", {"m_payment_id": m_payment_id})
			if not payfast_order:
				frappe.log_error(f"PayFast Order not found for m_payment_id: {m_payment_id}", "PayFast ITN Error")
				return False
			
			# Get the order and process ITN
			order_doc = frappe.get_doc("PayFast Order", payfast_order)
			success = order_doc.handle_itn_notification(itn_data)
			
			if success:
				frappe.log_error(
					f"PayFast ITN processed successfully for order {payfast_order}",
					"PayFast ITN Success"
				)
			
			return success
			
		except Exception as e:
			frappe.log_error(
				f"Error processing PayFast ITN: {str(e)}\n{frappe.get_traceback()}",
				"PayFast ITN Processing Error"
			)
			return False

	def _get_signature(self, data, passphrase):
		"""Generate PayFast signature"""
		# Create URL encoded string
		data = dict(sorted(data.items()))
		pf_output = "&".join(f"{k}={quote_plus(str(v))}" for k, v in data.items())
		if passphrase:
			pf_output += f"&passphrase={passphrase}"
		return hashlib.md5(pf_output.encode("utf-8")).hexdigest()

	def verify_itn_signature(self, itn_data):
		"""Verify PayFast ITN signature"""
		try:
			passphrase = self.get_password("passphrase", raise_exception=False)
			received_signature = itn_data.pop("signature", "")
			
			if not received_signature:
				return False
			
			expected_signature = self._get_signature(itn_data, passphrase)
			
			# Add signature back to data
			itn_data["signature"] = received_signature
			
			return expected_signature == received_signature
			
		except Exception as e:
			frappe.log_error(
				f"Error verifying PayFast ITN signature: {str(e)}",
				"PayFast Signature Verification Error"
			)
			return False


# Legacy ITN handler - keep for backward compatibility but mark as deprecated
@frappe.whitelist(allow_guest=True)
def payfast_itn():
	"""
	Legacy ITN callback from PayFast - deprecated.
	Use handle_itn() instead which follows ERPNext compliance patterns.
	"""
	frappe.log_error(
		"payfast_itn called - this function is deprecated. "
		"Use handle_itn() instead which follows ERPNext patterns.",
		"PayFast ITN Deprecated Function"
	)
	
	try:
		frappe.log_error("Payfast ITN called", frappe.local.form_dict)
		# get the posted data from payfast
		data = frappe.local.form_dict

		# get the payment gateway controller
		# custom_str1 should be the name of the payfast settings doc
		controller = frappe.get_doc("Payfast Settings", data.get("custom_str1"))

		# verify the signature
		if not controller.verify_itn_signature(data.copy()):
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
