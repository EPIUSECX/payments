# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""
PayFast Order DocType for tracking payment transactions.

This module manages PayFast payment orders, handling ITN notifications,
signature verification, and payment status updates.
"""

import json

import frappe
from frappe import _
from frappe.model.document import Document

# Import PayFast utilities and constants
from payments.payment_gateways.doctype.payfast_settings.payfast_utils import (
    verify_itn_signature,
    get_payfast_settings,
)
from payments.payment_gateways.doctype.payfast_settings.payfast_constants import (
    ORDER_STATUS_PENDING,
    ORDER_STATUS_COMPLETE,
    ORDER_STATUS_FAILED,
    ORDER_STATUS_CANCELLED,
    PAYMENT_STATUS_COMPLETE,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_CANCELLED,
    SUPPORTED_CURRENCY,
)


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
		currency: str = SUPPORTED_CURRENCY,
		item_name: str = None,
		meta_data: dict | None = None,
		ref_dt: str | None = None,
		ref_dn: str | None = None,
	) -> dict:
		"""
		Create a new PayFast Order record for tracking payment.
		
		Args:
			m_payment_id: Unique merchant payment ID (typically Integration Request name)
			amount_gross: Total payment amount
			currency: Transaction currency (default: ZAR)
			item_name: Name/description of item being purchased
			meta_data: Additional metadata to store
			ref_dt: Reference doctype (e.g., "Sales Invoice")
			ref_dn: Reference document name
			
		Returns:
			dict: Order details including order name and payment ID
		"""
		if meta_data is None:
			meta_data = {}
		
		order_doc = frappe.get_doc(
			doctype="PayFast Order",
			m_payment_id=m_payment_id,
			amount_gross=amount_gross,
			currency=currency,
			item_name=item_name,
			meta_data=frappe.as_json(meta_data, indent=2),
			status=ORDER_STATUS_PENDING,
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
		"""
		Handle ITN (Instant Transaction Notification) from PayFast.
		
		This method processes the ITN, verifies the signature, updates order status,
		and triggers payment completion for the reference document.
		
		Args:
			itn_data: Dictionary containing ITN data from PayFast
			
		Returns:
			bool: True if ITN processed successfully, False otherwise
		"""
		try:
			# Get PayFast settings for signature verification
			settings_name = itn_data.get("custom_str1")
			if not settings_name:
				frappe.log_error(
					f"PayFast ITN missing settings reference for order {self.name}",
					"PayFast Order ITN Error"
				)
				self.mark_as_failed("ITN missing settings reference")
				return False
			
			settings = frappe.get_doc("Payfast Settings", settings_name)
			passphrase = settings.get_password("passphrase", raise_exception=False)
			
			# CRITICAL: Verify signature using utility function
			signature_valid = verify_itn_signature(itn_data, passphrase)
			
			frappe.log_error(
				f"[ITN DEBUG] Signature Verification:\n"
				f"Order: {self.name}\n"
				f"Settings: {settings_name}\n"
				f"Signature Valid: {signature_valid}\n"
				f"Provided Signature: {itn_data.get('signature')}\n"
				f"Has Passphrase: {bool(passphrase)}",
				"PayFast ITN Signature Check"
			)
			
			if not signature_valid:
				frappe.log_error(
					f"PayFast ITN signature verification failed for order {self.name}",
					"PayFast Order ITN Error"
				)
				self.mark_as_failed("ITN signature verification failed")
				return False
	
			# Update order with ITN data
			self.update_from_itn_data(itn_data)
			
			# Process based on payment status using constants
			payment_status = itn_data.get("payment_status")
			
			if payment_status == PAYMENT_STATUS_COMPLETE:
				self.mark_as_complete(itn_data)
				self.trigger_payment_completion()
			elif payment_status == PAYMENT_STATUS_FAILED:
				self.mark_as_failed("Payment failed at PayFast")
			elif payment_status == PAYMENT_STATUS_CANCELLED:
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
		"""
		Update order fields from ITN data.
		
		Args:
			itn_data: Dictionary containing ITN data from PayFast
		"""
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
		
		# Store complete ITN data in meta_data for audit trail
		existing_meta = json.loads(self.meta_data or "{}")
		existing_meta["itn_data"] = itn_data
		existing_meta["itn_received_at"] = frappe.utils.now()
		self.meta_data = frappe.as_json(existing_meta, indent=2)

	def verify_itn_signature(self, itn_data: dict) -> bool:
		"""
		Verify PayFast ITN signature.
		
		DEPRECATED: This method is deprecated. Use payfast_utils.verify_itn_signature() instead.
		Kept for backward compatibility only.
		
		Args:
			itn_data: Dictionary containing ITN data from PayFast
			
		Returns:
			bool: True if signature is valid, False otherwise
		"""
		frappe.log_error(
			f"PayFastOrder.verify_itn_signature() called for order {self.name}. "
			"This method is deprecated. Use payfast_utils.verify_itn_signature() instead.",
			"PayFast Order Deprecated Method"
		)
		
		# Get settings from ITN data
		settings_name = itn_data.get("custom_str1")
		if not settings_name:
			return False
		
		try:
			settings = frappe.get_doc("Payfast Settings", settings_name)
			passphrase = settings.get_password("passphrase", raise_exception=False)
			return verify_itn_signature(itn_data, passphrase)
		except Exception as e:
			frappe.log_error(
				f"Error in deprecated verify_itn_signature: {str(e)}",
				"PayFast Order Signature Error"
			)
			return False

	def mark_as_complete(self, itn_data: dict = None):
		"""
		Mark order as complete with payment details.
		
		Args:
			itn_data: Optional ITN data for additional logging
		"""
		self.status = ORDER_STATUS_COMPLETE
		self.save(ignore_permissions=True)
		
		frappe.log_error(
			f"PayFast Order {self.name} marked as complete\nAmount: {self.amount_gross} {self.currency}",
			"PayFast Order Completed"
		)

	def mark_as_failed(self, error_message: str = None):
		"""
		Mark order as failed.
		
		Args:
			error_message: Optional error message to store
		"""
		self.status = ORDER_STATUS_FAILED
		
		if error_message:
			meta_data = json.loads(self.meta_data or "{}")
			meta_data["error_message"] = error_message
			meta_data["failed_at"] = frappe.utils.now()
			self.meta_data = frappe.as_json(meta_data, indent=2)
		
		self.save(ignore_permissions=True)
		
		frappe.log_error(
			f"PayFast Order {self.name} marked as failed\nReason: {error_message}",
			"PayFast Order Failed"
		)

	def mark_as_cancelled(self, reason: str = None):
		"""
		Mark order as cancelled.
		
		Args:
			reason: Optional reason for cancellation
		"""
		self.status = ORDER_STATUS_CANCELLED
		
		if reason:
			meta_data = json.loads(self.meta_data or "{}")
			meta_data["cancellation_reason"] = reason
			meta_data["cancelled_at"] = frappe.utils.now()
			self.meta_data = frappe.as_json(meta_data, indent=2)
		
		self.save(ignore_permissions=True)
		
		frappe.log_error(
			f"PayFast Order {self.name} cancelled\nReason: {reason}",
			"PayFast Order Cancelled"
		)

	def trigger_payment_completion(self):
		"""
		Trigger ERPNext payment completion for linked reference documents.
		
		This method calls the on_payment_authorized hook on the reference document
		to complete the payment workflow (e.g., marking invoice as paid).
		"""
		frappe.log_error(
			f"[ITN DEBUG] trigger_payment_completion called:\n"
			f"Order: {self.name}\n"
			f"ref_dt: {self.ref_dt}\n"
			f"ref_dn: {self.ref_dn}\n"
			f"m_payment_id: {self.m_payment_id}\n"
			f"amount_gross: {self.amount_gross}\n"
			f"status: {self.status}",
			"PayFast ITN Payment Completion Start"
		)
		
		if not (self.ref_dt and self.ref_dn):
			frappe.log_error(
				f"PayFast Order {self.name} has no reference document to complete\n"
				f"ref_dt: {self.ref_dt}, ref_dn: {self.ref_dn}\n"
				f"This order cannot trigger payment completion without reference document!",
				"PayFast Order No Reference"
			)
			return
			
		try:
			ref_doc = frappe.get_doc(self.ref_dt, self.ref_dn)
			
			frappe.log_error(
				f"[ITN DEBUG] Reference Document Loaded:\n"
				f"DocType: {self.ref_dt}\n"
				f"DocName: {self.ref_dn}\n"
				f"Has on_payment_authorized: {hasattr(ref_doc, 'on_payment_authorized')}\n"
				f"Document Status: {getattr(ref_doc, 'status', 'N/A')}\n"
				f"Document docstatus: {getattr(ref_doc, 'docstatus', 'N/A')}",
				"PayFast ITN Reference Document Check"
			)
			
			if hasattr(ref_doc, 'on_payment_authorized'):
				frappe.log_error(
					f"[ITN DEBUG] Calling on_payment_authorized('Completed') on {self.ref_dt} {self.ref_dn}",
					"PayFast ITN Calling Payment Method"
				)
				
				ref_doc.run_method("on_payment_authorized", "Completed")
				frappe.db.commit()
				
				frappe.log_error(
					f"[ITN DEBUG] Payment completion SUCCESS!\n"
					f"Called on_payment_authorized on {self.ref_dt} {self.ref_dn}\n"
					f"Changes committed to database",
					"PayFast Payment Completion Success"
				)
			else:
				frappe.log_error(
					f"[ITN DEBUG] PROBLEM: {self.ref_dt} does not have on_payment_authorized method\n"
					f"Available methods: {[m for m in dir(ref_doc) if not m.startswith('_')]}",
					"PayFast Payment Completion Warning"
				)
		except Exception as e:
			frappe.log_error(
				f"[ITN DEBUG] ERROR triggering payment completion:\n"
				f"DocType: {self.ref_dt}\n"
				f"DocName: {self.ref_dn}\n"
				f"Error: {str(e)}\n{frappe.get_traceback()}",
				"PayFast Order Payment Completion Error"
			)

	@property
	def is_complete(self) -> bool:
		"""Check if order is complete."""
		return self.status == ORDER_STATUS_COMPLETE

	@property
	def is_failed(self) -> bool:
		"""Check if order failed."""
		return self.status == ORDER_STATUS_FAILED

	@property
	def is_cancelled(self) -> bool:
		"""Check if order was cancelled."""
		return self.status == ORDER_STATUS_CANCELLED

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
		"""
		Validate PayFast Order before save.
		
		Ensures required fields are present and data is valid.
		"""
		# Ensure m_payment_id is provided
		if not self.m_payment_id:
			frappe.throw(_("Merchant Payment ID is required"))

		# Validate amount
		if self.amount_gross and self.amount_gross <= 0:
			frappe.throw(_("Amount must be greater than zero"))

		# Ensure currency is ZAR for PayFast (using constant)
		if self.currency and self.currency != SUPPORTED_CURRENCY:
			frappe.throw(
				_("PayFast only supports {0} currency").format(SUPPORTED_CURRENCY)
			)

	def on_update(self):
		"""
		Called after save.
		
		Automatically links order to Integration Request and updates its status.
		"""
		# Auto-link to Integration Request if we can find it
		if not hasattr(self, '_integration_request_linked'):
			self.auto_link_integration_request()

	def auto_link_integration_request(self):
		"""
		Automatically link to Integration Request based on m_payment_id.
		
		Updates Integration Request status when order is complete.
		"""
		try:
			if self.m_payment_id and frappe.db.exists("Integration Request", self.m_payment_id):
				# Update Integration Request status if this order is complete
				if self.status == ORDER_STATUS_COMPLETE:
					integration_request = frappe.get_doc("Integration Request", self.m_payment_id)
					if integration_request.status != "Completed":
						integration_request.update_status({}, "Completed")
						frappe.log_error(
							f"Integration Request {self.m_payment_id} marked as Completed",
							"PayFast Order Integration Link"
						)
				
				self._integration_request_linked = True
	                       
		except Exception as e:
			# Don't fail the order save if auto-linking fails
			frappe.log_error(
				f"Failed to auto-link Integration Request for PayFast Order {self.name}: {str(e)}\n{frappe.get_traceback()}",
				"PayFast Order Auto-Link Error"
			)