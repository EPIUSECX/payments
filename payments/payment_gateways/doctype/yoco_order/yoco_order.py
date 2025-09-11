# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

import hashlib
import hmac
import json

import frappe
from frappe import _
from frappe.model.document import Document


class YocoOrder(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        amount: DF.Currency
        currency: DF.Link | None
        customer_email: DF.Data | None
        customer_phone: DF.Data | None
        fee: DF.Currency
        meta_data: DF.Code | None
        order_id: DF.Data
        payment_id: DF.Data | None
        payment_method: DF.Data | None
        ref_dn: DF.DynamicLink | None
        ref_dt: DF.Link | None
        refund_id: DF.Data | None
        status: DF.Literal["Pending", "Authorized", "Completed", "Failed", "Cancelled", "Refunded"]
        yoco_charge_id: DF.Data | None
    # end: auto-generated types

    @staticmethod
    def create_order(
        amount: float,
        currency: str = "ZAR",
        meta_data: dict | None = None,
        ref_dt: str | None = None,
        ref_dn: str | None = None,
    ) -> dict:
        """Create a new Yoco Order record for tracking payment"""
        if meta_data is None:
            meta_data = {}
        
        # Generate unique order ID
        import uuid
        order_id = f"yoco_order_{uuid.uuid4().hex[:16]}"
        
        order_doc = frappe.get_doc(
            doctype="Yoco Order",
            order_id=order_id,
            amount=amount,
            currency=currency,
            meta_data=frappe.as_json(meta_data, indent=2),
            status="Pending",
            ref_dt=ref_dt,
            ref_dn=ref_dn,
        )
        order_doc.insert(ignore_permissions=True)
        
        return {
            "order_id": order_id,
            "amount": amount,
            "currency": currency,
            "yoco_order": order_doc.name
        }

    def handle_webhook_event(self, event_type: str, webhook_payload: dict):
        """Handle webhook events from Yoco"""
        try:
            if event_type == "charge.succeeded":
                self.handle_charge_succeeded(webhook_payload)
            elif event_type == "charge.failed":
                self.handle_charge_failed(webhook_payload)
            elif event_type == "charge.refunded":
                self.handle_charge_refunded(webhook_payload)
            else:
                frappe.log_error(
                    f"Unhandled Yoco webhook event: {event_type}",
                    "Yoco Order Webhook"
                )
        except Exception as e:
            frappe.log_error(
                f"Error handling Yoco webhook event {event_type}: {str(e)}\n{frappe.get_traceback()}",
                "Yoco Order Webhook Error"
            )
            raise

    def handle_charge_succeeded(self, payload: dict):
        """Handle successful charge webhook"""
        charge_data = payload.get("data", {}).get("object", {})
        
        self.status = "Completed"
        self.payment_id = charge_data.get("id")
        self.yoco_charge_id = charge_data.get("id")
        self.customer_email = charge_data.get("receipt", {}).get("email")
        self.payment_method = charge_data.get("source", {}).get("type")
        
        # Set fee if available
        if charge_data.get("fee"):
            self.fee = charge_data.get("fee") / 100  # Convert from cents
        
        self.save(ignore_permissions=True)
        
        # Trigger ERPNext payment completion
        self.trigger_payment_completion()

    def handle_charge_failed(self, payload: dict):
        """Handle failed charge webhook"""
        self.status = "Failed"
        self.save(ignore_permissions=True)

    def handle_charge_refunded(self, payload: dict):
        """Handle refund webhook"""
        refund_data = payload.get("data", {}).get("object", {})
        
        self.status = "Refunded"
        self.refund_id = refund_data.get("id")
        self.save(ignore_permissions=True)

    def trigger_payment_completion(self):
        """Trigger ERPNext payment completion for linked documents"""
        if not (self.ref_dt and self.ref_dn):
            return
            
        try:
            ref_doc = frappe.get_doc(self.ref_dt, self.ref_dn)
            if hasattr(ref_doc, 'on_payment_authorized'):
                ref_doc.run_method("on_payment_authorized", "Completed")
        except Exception as e:
            frappe.log_error(
                f"Error triggering payment completion for {self.ref_dt} {self.ref_dn}: {str(e)}",
                "Yoco Order Payment Completion Error"
            )

    def mark_as_paid(self, payment_data: dict = None):
        """Mark order as paid with payment details"""
        self.status = "Completed"
        
        if payment_data:
            self.payment_id = payment_data.get("id")
            self.yoco_charge_id = payment_data.get("id")
            self.customer_email = payment_data.get("receipt", {}).get("email")
            self.payment_method = payment_data.get("source", {}).get("type")
            
            if payment_data.get("fee"):
                self.fee = payment_data.get("fee") / 100
                
        self.save(ignore_permissions=True)
        self.trigger_payment_completion()

    def mark_as_failed(self, error_message: str = None):
        """Mark order as failed"""
        self.status = "Failed"
        
        if error_message:
            meta_data = json.loads(self.meta_data or "{}")
            meta_data["error_message"] = error_message
            self.meta_data = frappe.as_json(meta_data, indent=2)
            
        self.save(ignore_permissions=True)

    def verify_webhook_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Verify Yoco webhook signature"""
        if not signature or not secret:
            return False
            
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)

    @property
    def is_paid(self) -> bool:
        """Check if order is paid"""
        return self.status == "Completed"

    @property
    def is_failed(self) -> bool:
        """Check if order failed"""
        return self.status == "Failed"

    @property
    def is_refunded(self) -> bool:
        """Check if order is refunded"""
        return self.status == "Refunded"

    @frappe.whitelist()
    def refund_payment(self):
        """Refund the payment (placeholder - implement Yoco API call)"""
        frappe.only_for("System Manager")
        
        if not self.is_paid:
            frappe.throw(_("Can only refund completed payments"))
            
        # TODO: Implement actual Yoco refund API call
        frappe.msgprint(_("Refund functionality not yet implemented. Please process refund through Yoco dashboard."))
        
    @frappe.whitelist()
    def sync_status(self):
        """Sync status with Yoco (placeholder - implement Yoco API call)"""
        frappe.only_for("System Manager")
        
        # TODO: Implement Yoco API status check
        frappe.msgprint(_("Status sync functionality not yet implemented."))