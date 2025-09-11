# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

import hashlib
import hmac
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
		"""ERPNext compliant payment gateway registration"""
		create_payment_gateway(
			"Yoco-" + self.name,
			settings="Yoco Settings",
			controller=self.name,
		)
		call_hook_method("payment_gateway_enabled", gateway="Yoco-" + self.name)

	def validate(self):
		"""Validate Yoco settings"""
		if not self.flags.ignore_mandatory:
			self.validate_yoco_credentials()

	def validate_yoco_credentials(self):
		"""Validate Yoco API credentials"""
		if self.public_key and self.get_password("secret_key", raise_exception=False):
			try:
				# Test API credentials with a simple API call
				self.test_connection()
			except Exception:
				frappe.throw(_("Invalid Yoco API credentials. Please check your API keys."))

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
		"""Validate currency is supported"""
		if currency not in self.supported_currencies:
			frappe.throw(
				_(
					"Please select another payment method. Yoco does not support transactions in currency '{0}'"
				).format(currency)
			)

	def validate_minimum_transaction_amount(self, currency, amount):
		"""Validate minimum transaction amount"""
		# Minimum transaction amount is R1.00 (100 cents)
		minimum_amount = 1.00

		if flt(amount) < minimum_amount:
			frappe.throw(
				_("For currency {0}, the minimum transaction amount should be {1}").format(
					currency, minimum_amount
				)
			)

	def get_payment_url(self, **kwargs):
		"""Get payment URL using Integration Request pattern"""
		integration_request = create_request_log(kwargs, service_name="Yoco")
		return get_url(f"./yoco_checkout?token={integration_request.name}")

	def create_request(self, data):
		"""
		ERPNext-compliant request creation using Integration Request pattern
		"""
		self.data = frappe._dict(data)

		try:
			# Create Integration Request for tracking
			self.integration_request = create_request_log(self.data, service_name="Yoco")
			
			# Create Yoco Order for transaction tracking
			yoco_order_data = self.create_yoco_order()
			
			# Return payment processing URL
			return self.finalize_request(yoco_order_data)

		except Exception as e:
			frappe.log_error(
				f"Yoco request creation failed: {str(e)}\n{frappe.get_traceback()}",
				"Yoco Request Creation Error"
			)
			return {
				"redirect_to": frappe.redirect_to_message(
					_("Server Error"),
					_(
						"There is an issue with the server's Yoco configuration. In case of failure, the amount will get refunded to your account."
					),
				),
				"status": 401,
			}

	def create_yoco_order(self):
		"""Create YocoOrder record for transaction tracking"""
		from payments.payment_gateways.doctype.yoco_order.yoco_order import YocoOrder
		
		order_data = YocoOrder.create_order(
			amount=self.data.amount,
			currency=self.data.currency or "ZAR",
			meta_data={
				"integration_request": self.integration_request.name,
				"reference_doctype": self.data.reference_doctype,
				"reference_docname": self.data.reference_docname
			},
			ref_dt=self.data.reference_doctype,
			ref_dn=self.data.reference_docname
		)
		
		return order_data

	def finalize_request(self, yoco_order_data=None):
		"""Finalize payment request and return appropriate redirect"""
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
				except Exception as e:
					frappe.log_error(
						f"Error in payment authorization callback: {str(e)}\n{frappe.get_traceback()}",
						"Yoco Payment Authorization Error"
					)

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

	def handle_webhook_event(self, event_type, payload):
		"""Handle webhook events with proper logging and error handling"""
		from payments.payment_gateways.doctype.yoco_webhook_log.yoco_webhook_log import YocoWebhookLog
		
		# Create webhook log for audit trail
		webhook_log = YocoWebhookLog.create_webhook_log(event_type, payload)
		
		try:
			webhook_log.mark_as_processing()
			
			# Process the webhook event
			if event_type == "charge.succeeded":
				self.handle_charge_succeeded(payload, webhook_log)
			elif event_type == "charge.failed":
				self.handle_charge_failed(payload, webhook_log)
			elif event_type == "charge.refunded":
				self.handle_charge_refunded(payload, webhook_log)
			else:
				frappe.log_error(
					f"Unhandled Yoco webhook event: {event_type}",
					"Yoco Webhook Handler"
				)
				webhook_log.mark_as_failed(f"Unhandled event type: {event_type}")
				return
			
			webhook_log.mark_as_completed()
			
		except Exception as e:
			error_msg = str(e)
			traceback_msg = frappe.get_traceback()
			
			frappe.log_error(
				f"Yoco webhook processing failed: {error_msg}\n{traceback_msg}",
				"Yoco Webhook Processing Error"
			)
			
			webhook_log.mark_as_failed(error_msg, traceback_msg)
			raise

	def handle_charge_succeeded(self, payload, webhook_log):
		"""Handle successful charge webhook"""
		charge_data = payload.get("data", {}).get("object", {})
		metadata = charge_data.get("metadata", {})
		
		# Find associated YocoOrder
		integration_request_id = metadata.get("integration_request")
		yoco_order = self.find_yoco_order(charge_data, metadata)
		
		if yoco_order:
			yoco_order.handle_webhook_event("charge.succeeded", payload)
			webhook_log.yoco_order = yoco_order.name
		elif integration_request_id:
			# Fallback: process via Integration Request
			self.process_integration_request(integration_request_id, payload)
		else:
			frappe.log_error(
				"No Yoco Order or Integration Request found for successful charge",
				"Yoco Webhook Processing Warning"
			)

	def handle_charge_failed(self, payload, webhook_log):
		"""Handle failed charge webhook"""
		charge_data = payload.get("data", {}).get("object", {})
		metadata = charge_data.get("metadata", {})
		
		yoco_order = self.find_yoco_order(charge_data, metadata)
		
		if yoco_order:
			yoco_order.handle_webhook_event("charge.failed", payload)
			webhook_log.yoco_order = yoco_order.name

	def handle_charge_refunded(self, payload, webhook_log):
		"""Handle refund webhook"""
		refund_data = payload.get("data", {}).get("object", {})
		charge_id = refund_data.get("charge")
		
		# Find YocoOrder by charge ID
		yoco_order = frappe.get_doc("Yoco Order", {"yoco_charge_id": charge_id}) if charge_id else None
		
		if yoco_order:
			yoco_order.handle_webhook_event("charge.refunded", payload)
			webhook_log.yoco_order = yoco_order.name

	def find_yoco_order(self, charge_data, metadata):
		"""Find YocoOrder from webhook data"""
		# Try to find by order_id in metadata
		order_id = metadata.get("order_id")
		if order_id:
			yoco_order = frappe.db.get_value("Yoco Order", {"order_id": order_id})
			if yoco_order:
				return frappe.get_doc("Yoco Order", yoco_order)
		
		# Try to find by charge ID
		charge_id = charge_data.get("id")
		if charge_id:
			yoco_order = frappe.db.get_value("Yoco Order", {"yoco_charge_id": charge_id})
			if yoco_order:
				return frappe.get_doc("Yoco Order", yoco_order)
		
		return None

	def process_integration_request(self, integration_request_id, payload):
		"""Process payment via Integration Request (fallback method)"""
		try:
			integration_request = frappe.get_doc("Integration Request", integration_request_id)
			request_data = json.loads(integration_request.data)
			
			# Update Integration Request status
			integration_request.update_status(payload, "Completed")
			
			# Process payment if this is a Payment Request
			if request_data.get("reference_doctype") == "Payment Request":
				payment_request_id = request_data.get("reference_docname")
				
				if payment_request_id:
					pr = frappe.get_doc("Payment Request", payment_request_id)
					pr.run_method("on_payment_authorized", "Completed")
					frappe.db.commit()
					
		except Exception as e:
			frappe.log_error(
				f"Error processing Integration Request {integration_request_id}: {str(e)}",
				"Yoco Integration Request Processing Error"
			)

	def verify_webhook_signature(self, payload, signature, secret):
		"""Verify the signature of the incoming webhook."""
		if not signature or not secret:
			return False
		
		generated_signature = hmac.new(
			secret.encode('utf-8'),
			payload,
			hashlib.sha256
		).hexdigest()
		
		return hmac.compare_digest(generated_signature, signature)

	def process_payment_completion(self, payment_data: dict, integration_request):
		"""
		Process payment completion - moved from template to controller for ERPNext compliance
		"""
		try:
			# Update Integration Request status
			integration_request.update_status(payment_data, "Completed")
			
			# Create or update YocoOrder
			yoco_order = self.create_or_update_yoco_order(payment_data, integration_request)
			
			# Process ERPNext payment workflow
			if payment_data.get("reference_doctype") == "Payment Request":
				payment_request_id = payment_data.get("reference_docname")
				
				if payment_request_id:
					payment_request = frappe.get_doc("Payment Request", payment_request_id)
					
					# Call the payment authorization method
					custom_redirect_to = payment_request.run_method("on_payment_authorized", "Completed")
					
					frappe.log_error(
						f"Payment Request {payment_request_id} processed successfully via Yoco",
						"Yoco Payment Success"
					)
					
					frappe.db.commit()
					
					# Return success redirect
					redirect_url = f"payment-success?doctype={payment_data['reference_doctype']}&docname={payment_request_id}"
					
					if custom_redirect_to:
						redirect_url = custom_redirect_to
					
					return {
						"redirect_to": redirect_url,
						"status": "Completed",
						"yoco_order": yoco_order.name if yoco_order else None
					}
				else:
					frappe.throw(_("Payment Request not found"))
			else:
				frappe.throw(_("Invalid reference document type"))
				
		except Exception as e:
			frappe.log_error(
				f"Yoco payment completion processing failed: {str(e)}\n{frappe.get_traceback()}",
				"Yoco Payment Completion Error"
			)
			
			# Update Integration Request as failed
			integration_request.update_status(payment_data, "Failed")
			
			return {
				"redirect_to": "payment-failed",
				"status": "Failed",
				"error": str(e)
			}

	def create_or_update_yoco_order(self, payment_data: dict, integration_request):
		"""Create or update YocoOrder from payment data"""
		try:
			from payments.payment_gateways.doctype.yoco_order.yoco_order import YocoOrder
			
			# Try to find existing YocoOrder via Integration Request
			request_data = json.loads(integration_request.data)
			
			# Look for existing order by integration request ID
			existing_order = frappe.db.get_value(
				"Yoco Order", 
				{"order_id": {"like": f"%{integration_request.name}%"}},
				"name"
			)
			
			if existing_order:
				yoco_order = frappe.get_doc("Yoco Order", existing_order)
				yoco_order.mark_as_paid({
					"id": payment_data.get("yoco_token_id"),
					"status": "succeeded"
				})
			else:
				# Create new YocoOrder
				order_data = YocoOrder.create_order(
					amount=request_data.get("amount", 0),
					currency=request_data.get("currency", "ZAR"),
					meta_data={
						"integration_request": integration_request.name,
						"yoco_token_id": payment_data.get("yoco_token_id"),
						"payment_details": payment_data.get("payment_details", {})
					},
					ref_dt=payment_data.get("reference_doctype"),
					ref_dn=payment_data.get("reference_docname")
				)
				
				yoco_order = frappe.get_doc("Yoco Order", order_data.get("yoco_order"))
				yoco_order.mark_as_paid({
					"id": payment_data.get("yoco_token_id"),
					"status": "succeeded"
				})
			
			return yoco_order
			
		except Exception as e:
			frappe.log_error(
				f"Failed to create/update YocoOrder: {str(e)}\n{frappe.get_traceback()}",
				"Yoco Order Creation Error"
			)
			return None
