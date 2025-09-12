# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

import hashlib
import json
from urllib.parse import quote_plus

import frappe
from frappe import _
from frappe.model.document import Document


class PayFastOrder(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount_fee: DF.Currency
		amount_gross: DF.Currency
		amount_net: DF.Currency
		currency: DF.Link | None
		email_address: DF.Data | None
		item_description: DF.SmallText | None
		item_name: DF.Data | None
		m_payment_id: DF.Data
		merchant_id: DF.Data | None
		meta_data: DF.Code | None
		name_first: DF.Data | None
		name_last: DF.Data | None
		payment_method: DF.Data | None
		pf_payment_id: DF.Data | None
		ref_dn: DF.DynamicLink | None
		ref_dt: DF.Link | None
		signature_verification: DF.Check
		status: DF.Literal["Pending", "Complete", "Cancelled", "Failed"]
	# end: auto-generated types

	@staticmethod
	def create_order(
		m_payment_id: str,
		amount_gross: float,
		currency: str = "ZAR",
		item_name: str = None,
		meta_data: dict | None = None,
		ref_dt: str | None = None,
		ref_dn: str | None = None,
	) -> dict:
		"""Create a new PayFast Order record for tracking payment"""
		if meta_data is None:
			meta_data = {}
		
		order_doc = frappe.get_doc(
			doctype="PayFast Order",
			m_payment_id=m_payment_id,
			amount_gross=amount_gross,
			currency=currency,
			item_name=item_name,
			meta_data=frappe.as_json(meta_data, indent=2),
			status="Pending",
			ref_dt=ref_dt,
			ref_dn=ref_dn,
		)
		order_doc.insert(ignore_permissions=True)
		
		return {
			"payfast_order": order_doc.name,
			"m_payment_id": m_payment_id,
			"amount_gross": amount_gross,
			"currency": currency
		}

	def handle_itn_notification(self, itn_data: dict):
		"""Handle ITN (Instant Transaction Notification) from PayFast"""
		try:
			# Verify signature first
			if not self.verify_itn_signature(itn_data):
				frappe.log_error(
					f"PayFast ITN signature verification failed for order {self.name}",
					"PayFast Order ITN Error"
				)
				self.mark_as_failed("ITN signature verification failed")
				return False

			# Update order with ITN data
			self.update_from_itn_data(itn_data)
			
			# Process based on payment status
			payment_status = itn_data.get("payment_status")
			
			if payment_status == "COMPLETE":
				self.mark_as_complete(itn_data)
				self.trigger_payment_completion()
			elif payment_status == "FAILED":
				self.mark_as_failed("Payment failed at PayFast")
			elif payment_status == "CANCELLED":
				self.mark_as_cancelled("Payment cancelled by user")
			else:
				frappe.log_error(
					f"Unknown PayFast payment status: {payment_status}",
					"PayFast Order Status Warning"
				)
			
			return True
			
		except Exception as e:
			frappe.log_error(
				f"Error handling PayFast ITN for order {self.name}: {str(e)}\n{frappe.get_traceback()}",
				"PayFast Order ITN Processing Error"
			)
			self.mark_as_failed(str(e))
			return False

	def update_from_itn_data(self, itn_data: dict):
		"""Update order fields from ITN data"""
		self.pf_payment_id = itn_data.get("pf_payment_id")
		self.merchant_id = itn_data.get("merchant_id")
		self.amount_gross = float(itn_data.get("amount_gross", 0))
		self.amount_fee = float(itn_data.get("amount_fee", 0))
		self.amount_net = float(itn_data.get("amount_net", 0))
		self.name_first = itn_data.get("name_first")
		self.name_last = itn_data.get("name_last")
		self.email_address = itn_data.get("email_address")
		self.payment_method = itn_data.get("payment_method")
		self.item_name = itn_data.get("item_name")
		self.item_description = itn_data.get("item_description")
		self.signature_verification = 1
		
		# Store complete ITN data in meta_data
		existing_meta = json.loads(self.meta_data or "{}")
		existing_meta["itn_data"] = itn_data
		self.meta_data = frappe.as_json(existing_meta, indent=2)

	def verify_itn_signature(self, itn_data: dict) -> bool:
		"""Verify PayFast ITN signature"""
		try:
			# Get PayFast settings
			settings = frappe.get_single("Payfast Settings")
			passphrase = settings.get_password("passphrase", raise_exception=False)
			
			# Extract signature from data
			received_signature = itn_data.get("signature")
			if not received_signature:
				return False
			
			# Create data string for signature verification (excluding signature field)
			verification_data = {k: v for k, v in itn_data.items() if k != "signature"}
			sorted_data = sorted(verification_data.items())
			data_string = "&".join([f"{k}={quote_plus(str(v))}" for k, v in sorted_data])
			
			# Add passphrase if configured
			if passphrase:
				data_string += f"&passphrase={passphrase}"
			
			# Generate signature
			expected_signature = hashlib.md5(data_string.encode("utf-8")).hexdigest()
			
			return expected_signature == received_signature
			
		except Exception as e:
			frappe.log_error(
				f"Error verifying PayFast ITN signature: {str(e)}",
				"PayFast Order Signature Error"
			)
			return False

	def mark_as_complete(self, itn_data: dict = None):
		"""Mark order as complete with payment details"""
		self.status = "Complete"
		self.save(ignore_permissions=True)

	def mark_as_failed(self, error_message: str = None):
		"""Mark order as failed"""
		self.status = "Failed"
		
		if error_message:
			meta_data = json.loads(self.meta_data or "{}")
			meta_data["error_message"] = error_message
			self.meta_data = frappe.as_json(meta_data, indent=2)
		
		self.save(ignore_permissions=True)

	def mark_as_cancelled(self, reason: str = None):
		"""Mark order as cancelled"""
		self.status = "Cancelled"
		
		if reason:
			meta_data = json.loads(self.meta_data or "{}")
			meta_data["cancellation_reason"] = reason
			self.meta_data = frappe.as_json(meta_data, indent=2)
		
		self.save(ignore_permissions=True)

	def trigger_payment_completion(self):
		"""Trigger ERPNext payment completion for linked documents"""
		if not (self.ref_dt and self.ref_dn):
			return
			
		try:
			ref_doc = frappe.get_doc(self.ref_dt, self.ref_dn)
			if hasattr(ref_doc, 'on_payment_authorized'):
				ref_doc.run_method("on_payment_authorized", "Completed")
				frappe.db.commit()
		except Exception as e:
			frappe.log_error(
				f"Error triggering payment completion for {self.ref_dt} {self.ref_dn}: {str(e)}",
				"PayFast Order Payment Completion Error"
			)

	@property
	def is_complete(self) -> bool:
		"""Check if order is complete"""
		return self.status == "Complete"

	@property
	def is_failed(self) -> bool:
		"""Check if order failed"""
		return self.status == "Failed"

	@property
	def is_cancelled(self) -> bool:
		"""Check if order was cancelled"""
		return self.status == "Cancelled"

	@frappe.whitelist()
	def retry_payment_completion(self):
		"""Retry payment completion (admin only)"""
		frappe.only_for("System Manager")
		
		if not self.is_complete:
			frappe.throw(_("Can only retry completion for completed payments"))
		
		try:
			self.trigger_payment_completion()
			frappe.msgprint(_("Payment completion retried successfully"))
		except Exception as e:
			frappe.throw(_("Failed to retry payment completion: {0}").format(str(e)))

	def validate(self):
		"""Validate PayFast Order"""
		# Ensure m_payment_id is provided
		if not self.m_payment_id:
			frappe.throw(_("Merchant Payment ID is required"))

		# Validate amount
		if self.amount_gross and self.amount_gross <= 0:
			frappe.throw(_("Amount must be greater than zero"))

		# Ensure currency is ZAR for PayFast
		if self.currency and self.currency != "ZAR":
			frappe.throw(_("PayFast only supports ZAR currency"))

	def on_update(self):
		"""Called after save"""
		# Auto-link to Integration Request if we can find it
		if not hasattr(self, '_integration_request_linked'):
			self.auto_link_integration_request()

	def auto_link_integration_request(self):
		"""Automatically link to Integration Request based on m_payment_id"""
		try:
			if self.m_payment_id and frappe.db.exists("Integration Request", self.m_payment_id):
				# Update Integration Request status if this order is complete
				if self.status == "Complete":
					integration_request = frappe.get_doc("Integration Request", self.m_payment_id)
					if integration_request.status != "Completed":
						integration_request.update_status({}, "Completed")
				
				self._integration_request_linked = True
                        
		except Exception as e:
			# Don't fail the order save if auto-linking fails
			frappe.log_error(
				f"Failed to auto-link Integration Request for PayFast Order {self.name}: {str(e)}",
				"PayFast Order Auto-Link Error"
			)