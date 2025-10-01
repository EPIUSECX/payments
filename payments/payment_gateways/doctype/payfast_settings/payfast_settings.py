# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""
PayFast Settings DocType for managing PayFast payment gateway configuration.

This module handles PayFast payment gateway setup, payment request creation,
and ITN notification processing.

Reference: https://developers.payfast.co.za/docs
"""

import json

import frappe
from frappe import _
from frappe.integrations.utils import create_request_log
from frappe.model.document import Document
from frappe.utils import call_hook_method, flt, get_url

from payments.utils import create_payment_gateway
from .payfast_constants import (
    SUPPORTED_CURRENCY,
    MINIMUM_TRANSACTION_AMOUNT,
    PAYFAST_SANDBOX_URL,
    PAYFAST_LIVE_URL,
    PAYMENT_STATUS_COMPLETE,
)
from .payfast_utils import generate_payment_signature


class PayfastSettings(Document):
	"""PayFast Settings DocType for payment gateway configuration."""
	
	supported_currencies = (SUPPORTED_CURRENCY,)

	def on_update(self):
		"""
		Called after document save.
		
		Registers payment gateway with ERPNext and enables it.
		"""
		create_payment_gateway(
			"Payfast-" + self.name,
			settings="Payfast Settings",
			controller=self.name,
		)
		call_hook_method("payment_gateway_enabled", gateway="Payfast-" + self.name)

	def validate(self):
		"""
		Validate PayFast settings before save.
		
		Ensures all required credentials are configured.
		"""
		if not self.flags.ignore_mandatory:
			self.validate_payfast_credentials()
			self.validate_urls()

	def validate_payfast_credentials(self):
		"""
		Validate PayFast merchant credentials.
		
		Raises:
			frappe.ValidationError: If required credentials are missing
		"""
		if not self.merchant_id:
			frappe.throw(_("Merchant ID is required"))
		if not self.merchant_key:
			frappe.throw(_("Merchant Key is required"))

	def validate_urls(self):
		"""
		Validate configured URLs are accessible.
		
		Logs warnings if URLs appear invalid but doesn't block save.
		"""
		if self.notify_url:
			if not self.notify_url.startswith(('http://', 'https://')):
				frappe.msgprint(
					_("Notify URL should start with http:// or https://"),
					indicator="orange",
					alert=True
				)

	def validate_transaction_currency(self, currency):
		"""
		Validate that transaction currency is supported by PayFast.
		
		Args:
			currency: Currency code (e.g., "ZAR")
			
		Raises:
			frappe.ValidationError: If currency not supported
		"""
		if currency not in self.supported_currencies:
			frappe.throw(
				_(
					"Please select another payment method. PayFast does not support transactions in currency '{0}'"
				).format(currency)
			)

	def validate_minimum_transaction_amount(self, currency, amount):
		"""
		Validate transaction amount meets PayFast minimum requirements.
		
		Args:
			currency: Transaction currency
			amount: Transaction amount
			
		Raises:
			frappe.ValidationError: If amount below minimum
			
		Reference:
			https://developers.payfast.co.za/docs#transaction_amounts
		"""
		if flt(amount) < MINIMUM_TRANSACTION_AMOUNT:
			frappe.throw(
				_("For currency {0}, the minimum transaction amount should be {1}").format(
					currency, MINIMUM_TRANSACTION_AMOUNT
				)
			)

	def get_payment_url(self, **kwargs):
		"""
		Get PayFast payment checkout URL.
		
		Creates an Integration Request and returns URL to checkout page.
		
		Args:
			**kwargs: Payment details (amount, currency, reference, etc.)
			
		Returns:
			str: URL to PayFast checkout page
		"""
		import time
		start_time = time.time()
		
		frappe.log_error(
			f"[PAYFAST DEBUG] get_payment_url called on settings {self.name}\nArgs: {json.dumps(kwargs, indent=2, default=str)}",
			"PayFast Settings get_payment_url Debug"
		)
		
		try:
			step_time = time.time()
			frappe.log_error(f"[PAYFAST DEBUG] Creating Integration Request", "PayFast Settings Debug")
			integration_request = create_request_log(kwargs, service_name="PayFast")
			frappe.log_error(
				f"[PAYFAST DEBUG] Integration Request created: {integration_request.name} in {time.time() - step_time:.2f}s",
				"PayFast Settings Debug"
			)
			
			url = get_url(f"./payfast_checkout?token={integration_request.name}")
			total_time = time.time() - start_time
			
			frappe.log_error(
				f"[PAYFAST DEBUG] get_payment_url completed in {total_time:.2f}s\nReturning URL: {url}",
				"PayFast Settings Debug"
			)
			
			return url
			
		except Exception as e:
			total_time = time.time() - start_time
			frappe.log_error(
				f"[PAYFAST DEBUG] get_payment_url FAILED after {total_time:.2f}s\nError: {str(e)}\n{frappe.get_traceback()}",
				"PayFast Settings Error"
			)
			raise

	def create_request(self, data):
		"""
		Create payment request for PayFast.
		
		This method follows ERPNext's Integration Request pattern for payment processing.
		It creates both an Integration Request (for tracking) and a PayFast Order (for
		transaction management).
		
		Args:
			data: Payment request data containing amount, currency, reference documents, etc.
			
		Returns:
			dict: Contains payfast_url, form_data, and payfast_order for redirect
			
		Reference:
			https://developers.payfast.co.za/docs#integration_options
		"""
		import time
		start_time = time.time()
		
		self.data = frappe._dict(data)
		
		frappe.log_error(
			f"[PAYFAST DEBUG] create_request called on settings {self.name}\nData: {json.dumps(data, indent=2, default=str)}",
			"PayFast Settings create_request Debug"
		)

		try:
			# Validate currency and amount
			step_time = time.time()
			frappe.log_error(f"[PAYFAST DEBUG] Step 1: Validating currency and amount", "PayFast Settings Debug")
			self.validate_transaction_currency(self.data.get("currency", SUPPORTED_CURRENCY))
			self.validate_minimum_transaction_amount(
				self.data.get("currency", SUPPORTED_CURRENCY),
				self.data.amount
			)
			frappe.log_error(f"[PAYFAST DEBUG] Step 1 complete in {time.time() - step_time:.2f}s", "PayFast Settings Debug")
			
			# Create Integration Request for tracking
			step_time = time.time()
			frappe.log_error(f"[PAYFAST DEBUG] Step 2: Creating Integration Request", "PayFast Settings Debug")
			self.integration_request = create_request_log(self.data, service_name="PayFast")
			frappe.log_error(f"[PAYFAST DEBUG] Step 2 complete in {time.time() - step_time:.2f}s\nIR: {self.integration_request.name}", "PayFast Settings Debug")
			
			# Create PayFast Order for transaction tracking
			step_time = time.time()
			frappe.log_error(f"[PAYFAST DEBUG] Step 3: Creating PayFast Order", "PayFast Settings Debug")
			payfast_order_data = self.create_payfast_order()
			frappe.log_error(f"[PAYFAST DEBUG] Step 3 complete in {time.time() - step_time:.2f}s\nOrder: {payfast_order_data.get('payfast_order')}", "PayFast Settings Debug")
			
			# Generate PayFast payment form data
			step_time = time.time()
			frappe.log_error(f"[PAYFAST DEBUG] Step 4: Generating payment form", "PayFast Settings Debug")
			result = self.generate_payment_form(payfast_order_data)
			frappe.log_error(f"[PAYFAST DEBUG] Step 4 complete in {time.time() - step_time:.2f}s", "PayFast Settings Debug")
			
			total_time = time.time() - start_time
			frappe.log_error(
				f"[PAYFAST DEBUG] create_request completed in {total_time:.2f}s\nResult keys: {list(result.keys())}",
				"PayFast Settings Debug"
			)
			
			return result

		except Exception as e:
			total_time = time.time() - start_time
			frappe.log_error(
				f"[PAYFAST DEBUG] create_request FAILED after {total_time:.2f}s\nError: {str(e)}\n{frappe.get_traceback()}",
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
		"""
		Create PayFastOrder record for transaction tracking.
		
		Returns:
			dict: Order data including order name and payment ID
		"""
		import time
		start_time = time.time()
		
		frappe.log_error(
			f"[PAYFAST DEBUG] create_payfast_order starting\nIntegration Request: {self.integration_request.name}",
			"PayFast Settings create_payfast_order Debug"
		)
		
		try:
			step_time = time.time()
			frappe.log_error(f"[PAYFAST DEBUG] Importing PayFastOrder class", "PayFast Settings Debug")
			from payments.payment_gateways.doctype.payfast_order.payfast_order import PayFastOrder
			frappe.log_error(f"[PAYFAST DEBUG] Import complete in {time.time() - step_time:.2f}s", "PayFast Settings Debug")
			
			step_time = time.time()
			frappe.log_error(f"[PAYFAST DEBUG] Calling PayFastOrder.create_order()", "PayFast Settings Debug")
			order_data = PayFastOrder.create_order(
				m_payment_id=self.integration_request.name,
				amount_gross=self.data.amount,
				currency=self.data.get("currency") or SUPPORTED_CURRENCY,
				item_name=self.data.get("title", "Payment"),
				meta_data={
					"integration_request": self.integration_request.name,
					"reference_doctype": self.data.get("reference_doctype"),
					"reference_docname": self.data.get("reference_docname"),
					"description": self.data.get("description"),
					"created_at": frappe.utils.now(),
				},
				ref_dt=self.data.get("reference_doctype"),
				ref_dn=self.data.get("reference_docname")
			)
			frappe.log_error(
				f"[PAYFAST DEBUG] PayFast Order created in {time.time() - step_time:.2f}s\nOrder: {order_data.get('payfast_order')}",
				"PayFast Settings Debug"
			)
			
			total_time = time.time() - start_time
			frappe.log_error(f"[PAYFAST DEBUG] create_payfast_order completed in {total_time:.2f}s", "PayFast Settings Debug")
			
			return order_data
			
		except Exception as e:
			total_time = time.time() - start_time
			frappe.log_error(
				f"[PAYFAST DEBUG] create_payfast_order FAILED after {total_time:.2f}s\nError: {str(e)}\n{frappe.get_traceback()}",
				"PayFast Settings Error"
			)
			raise

	def generate_payment_form(self, payfast_order_data):
		"""
		Generate PayFast payment form data for POST redirect.
		
		Args:
			payfast_order_data: PayFast Order details from create_payfast_order()
			
		Returns:
			dict: Contains payfast_url, form_data dict, and payfast_order name
			
		Reference:
			https://developers.payfast.co.za/docs#step_1
		"""
		import time
		start_time = time.time()
		
		frappe.log_error(
			f"[PAYFAST DEBUG] generate_payment_form starting\nOrder data: {json.dumps(payfast_order_data, indent=2, default=str)}",
			"PayFast Settings generate_payment_form Debug"
		)
		
		try:
			# Prepare data for PayFast form
			step_time = time.time()
			frappe.log_error(f"[PAYFAST DEBUG] Step 1: Building form_data", "PayFast Settings Debug")
			
			form_data = {
				"merchant_id": self.merchant_id,
				"merchant_key": self.merchant_key,
				"name_first": self.data.get("payer_name", "").split(" ")[0] if self.data.get("payer_name") else "",
				"name_last": " ".join(self.data.get("payer_name", "").split(" ")[1:]) if self.data.get("payer_name") else "",
				"m_payment_id": payfast_order_data["m_payment_id"],
				"amount": "{:.2f}".format(flt(self.data.amount)),
				"item_name": self.data.get("title", "Payment"),
				"item_description": self.data.get("description", ""),
				"custom_str1": self.name,  # PayFast Settings document name for ITN routing
				"custom_str2": self.data.get("reference_docname", ""),  # Reference document name
			}
			frappe.log_error(f"[PAYFAST DEBUG] Step 1 complete in {time.time() - step_time:.2f}s", "PayFast Settings Debug")

			# Add optional fields
			step_time = time.time()
			frappe.log_error(f"[PAYFAST DEBUG] Step 2: Adding optional fields", "PayFast Settings Debug")
			if self.return_url:
				form_data["return_url"] = self.return_url
			if self.cancel_url:
				form_data["cancel_url"] = self.cancel_url
			if self.notify_url:
				form_data["notify_url"] = self.notify_url
			else:
				# Default ITN URL if not configured
				form_data["notify_url"] = get_url("/api/method/payments.payment_gateways.payfast_itn.handle_itn")
			
			# Add email if available
			email = self.data.get("payer_email")
			if not email and self.data.get("customer"):
				email = frappe.db.get_value("Customer", self.data.get("customer"), "email_id")
			if email:
				form_data["email_address"] = email
			frappe.log_error(f"[PAYFAST DEBUG] Step 2 complete in {time.time() - step_time:.2f}s", "PayFast Settings Debug")

			# Remove any empty values
			form_data = {k: v for k, v in form_data.items() if v}

			# Create signature using utility function
			step_time = time.time()
			frappe.log_error(f"[PAYFAST DEBUG] Step 3: Generating signature", "PayFast Settings Debug")
			passphrase = self.get_password("passphrase", raise_exception=False)
			form_data["signature"] = generate_payment_signature(form_data, passphrase)
			frappe.log_error(f"[PAYFAST DEBUG] Step 3 complete in {time.time() - step_time:.2f}s", "PayFast Settings Debug")

			# Generate PayFast URL using constants
			payfast_url = PAYFAST_SANDBOX_URL if self.sandbox_mode else PAYFAST_LIVE_URL
			
			result = {
				"payfast_url": payfast_url,
				"form_data": form_data,
				"payfast_order": payfast_order_data["payfast_order"]
			}
			
			total_time = time.time() - start_time
			frappe.log_error(
				f"[PAYFAST DEBUG] generate_payment_form completed in {total_time:.2f}s\nPayFast URL: {payfast_url}",
				"PayFast Settings Debug"
			)
			
			return result

		except Exception as e:
			total_time = time.time() - start_time
			frappe.log_error(
				f"[PAYFAST DEBUG] generate_payment_form FAILED after {total_time:.2f}s\nError: {str(e)}\n{frappe.get_traceback()}",
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

	def handle_itn_notification(self, itn_data: dict):
		"""
		Handle ITN (Instant Transaction Notification) from PayFast.
		
		This method routes the ITN to the appropriate PayFast Order for processing.
		All security validations (IP, signature, payment confirmation) are handled
		before this method is called.
		
		Args:
			itn_data: Dictionary containing ITN data from PayFast
			
		Returns:
			bool: True if ITN processed successfully, False otherwise
			
		Reference:
			https://developers.payfast.co.za/docs#itn
		"""
		try:
			# Log ITN received for this settings instance
			frappe.log_error(
				f"PayFast ITN received for settings {self.name}: {json.dumps(itn_data, indent=2)}",
				"PayFast ITN Received"
			)
			
			# Find PayFast Order by m_payment_id
			m_payment_id = itn_data.get("m_payment_id")
			if not m_payment_id:
				frappe.log_error("PayFast ITN missing m_payment_id", "PayFast ITN Error")
				return False
			
			payfast_order = frappe.db.get_value("PayFast Order", {"m_payment_id": m_payment_id})
			if not payfast_order:
				frappe.log_error(
					f"PayFast Order not found for m_payment_id: {m_payment_id}",
					"PayFast ITN Error"
				)
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
		"""
		Generate PayFast signature.
		
		DEPRECATED: Use payfast_utils.generate_payment_signature() instead.
		Kept for backward compatibility only.
		
		Args:
			data: Form data dictionary
			passphrase: Optional passphrase
			
		Returns:
			str: MD5 signature hash
		"""
		frappe.log_error(
			"PayfastSettings._get_signature() called. This method is deprecated. "
			"Use payfast_utils.generate_payment_signature() instead.",
			"PayFast Deprecated Method"
		)
		return generate_payment_signature(data, passphrase)

	def verify_itn_signature(self, itn_data):
		"""
		Verify PayFast ITN signature.
		
		DEPRECATED: Use payfast_utils.verify_itn_signature() instead.
		Kept for backward compatibility only.
		
		Args:
			itn_data: ITN data dictionary
			
		Returns:
			bool: True if signature valid, False otherwise
		"""
		from .payfast_utils import verify_itn_signature
		
		frappe.log_error(
			"PayfastSettings.verify_itn_signature() called. This method is deprecated. "
			"Use payfast_utils.verify_itn_signature() instead.",
			"PayFast Deprecated Method"
		)
		
		try:
			passphrase = self.get_password("passphrase", raise_exception=False)
			return verify_itn_signature(itn_data, passphrase)
		except Exception as e:
			frappe.log_error(
				f"Error in deprecated verify_itn_signature: {str(e)}",
				"PayFast Signature Verification Error"
			)
			return False


# Legacy ITN handler - keep for backward compatibility but mark as deprecated
@frappe.whitelist(allow_guest=True)
def payfast_itn():
	"""
	Legacy ITN callback from PayFast - DEPRECATED.
	
	This function is deprecated and will be removed in a future version.
	Use payments.payment_gateways.payfast_itn.handle_itn() instead which:
	- Implements all required security validations (IP, signature, confirmation)
	- Follows ERPNext compliance patterns
	- Provides better error handling and logging
	
	Reference:
		https://developers.payfast.co.za/docs#itn
	"""
	frappe.log_error(
		"payfast_itn() called - this function is DEPRECATED!\n"
		"Use payments.payment_gateways.payfast_itn.handle_itn() instead.\n"
		"This function will be removed in a future version.",
		"PayFast ITN Deprecated Function Warning"
	)
	
	# Redirect to new handler
	from payments.payment_gateways.payfast_itn import handle_itn
	return handle_itn()
