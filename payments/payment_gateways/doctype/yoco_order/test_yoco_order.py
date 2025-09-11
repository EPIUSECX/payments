# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase


class TestYocoOrder(FrappeTestCase):
    def setUp(self):
        """Set up test data"""
        # Create test YocoSettings if not exists
        if not frappe.db.exists("Yoco Settings", "Test Yoco"):
            yoco_settings = frappe.get_doc({
                "doctype": "Yoco Settings",
                "name": "Test Yoco",
                "public_key": "test_public_key",
                "secret_key": "test_secret_key",
                "webhook_secret": "test_webhook_secret",
                "sandbox_mode": 1
            })
            yoco_settings.insert(ignore_permissions=True)

        # Create test customer if not exists
        if not frappe.db.exists("Customer", "Test Customer"):
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "Test Customer",
                "customer_type": "Individual",
                "customer_group": "All Customer Groups",
                "territory": "All Territories"
            })
            customer.insert(ignore_permissions=True)

    def test_yoco_order_creation(self):
        """Test YocoOrder document creation"""
        order_data = frappe.get_doc({
            "doctype": "Yoco Order",
            "order_id": "test_order_123",
            "amount": 100.00,
            "currency": "ZAR",
            "status": "Pending"
        })
        order_data.insert()
        
        # Test that order was created with correct values
        self.assertEqual(order_data.status, "Pending")
        self.assertEqual(order_data.amount, 100.00)
        self.assertEqual(order_data.currency, "ZAR")
        self.assertTrue(order_data.name)

    def test_yoco_order_static_creation(self):
        """Test YocoOrder static creation method"""
        from payments.payment_gateways.doctype.yoco_order.yoco_order import YocoOrder
        
        result = YocoOrder.create_order(
            amount=150.00,
            currency="ZAR",
            ref_dt="Payment Request",
            ref_dn="TEST-PR-001"
        )
        
        # Verify result structure
        self.assertIn("order_id", result)
        self.assertIn("yoco_order", result)
        self.assertEqual(result["amount"], 150.00)
        self.assertEqual(result["currency"], "ZAR")
        
        # Verify order was created in database
        order = frappe.get_doc("Yoco Order", result["yoco_order"])
        self.assertEqual(order.amount, 150.00)
        self.assertEqual(order.ref_dt, "Payment Request")
        self.assertEqual(order.ref_dn, "TEST-PR-001")

    def test_webhook_event_handling(self):
        """Test webhook event handling"""
        # Create test order
        order = frappe.get_doc({
            "doctype": "Yoco Order",
            "order_id": "test_webhook_order",
            "amount": 200.00,
            "currency": "ZAR",
            "status": "Pending"
        })
        order.insert()
        
        # Test successful charge webhook
        webhook_payload = {
            "data": {
                "object": {
                    "id": "charge_test_123",
                    "receipt": {"email": "test@example.com"},
                    "source": {"type": "card"},
                    "fee": 500  # 5.00 ZAR in cents
                }
            }
        }
        
        order.handle_webhook_event("charge.succeeded", webhook_payload)
        order.reload()
        
        # Verify order was updated
        self.assertEqual(order.status, "Completed")
        self.assertEqual(order.payment_id, "charge_test_123")
        self.assertEqual(order.customer_email, "test@example.com")
        self.assertEqual(order.payment_method, "card")
        self.assertEqual(order.fee, 5.00)

    def test_signature_verification(self):
        """Test webhook signature verification"""
        order = frappe.get_doc({
            "doctype": "Yoco Order",
            "order_id": "test_signature_order",
            "amount": 100.00,
            "currency": "ZAR"
        })
        order.insert()
        
        # Test valid signature
        payload = "test_payload"
        secret = "test_secret"
        
        import hashlib
        import hmac
        valid_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        self.assertTrue(order.verify_webhook_signature(payload, valid_signature, secret))
        self.assertFalse(order.verify_webhook_signature(payload, "invalid_signature", secret))

    def test_order_status_properties(self):
        """Test order status properties"""
        order = frappe.get_doc({
            "doctype": "Yoco Order",
            "order_id": "test_status_order",
            "amount": 100.00,
            "currency": "ZAR",
            "status": "Pending"
        })
        order.insert()
        
        # Test initial status
        self.assertFalse(order.is_paid)
        self.assertFalse(order.is_failed)
        self.assertFalse(order.is_refunded)
        
        # Test completed status
        order.status = "Completed"
        order.save()
        self.assertTrue(order.is_paid)
        
        # Test failed status
        order.status = "Failed"
        order.save()
        self.assertTrue(order.is_failed)
        
        # Test refunded status
        order.status = "Refunded"
        order.save()
        self.assertTrue(order.is_refunded)

    def test_mark_as_paid(self):
        """Test marking order as paid"""
        order = frappe.get_doc({
            "doctype": "Yoco Order",
            "order_id": "test_paid_order",
            "amount": 100.00,
            "currency": "ZAR",
            "status": "Pending"
        })
        order.insert()
        
        payment_data = {
            "id": "payment_123",
            "receipt": {"email": "customer@test.com"},
            "source": {"type": "card"},
            "fee": 300  # 3.00 ZAR in cents
        }
        
        order.mark_as_paid(payment_data)
        order.reload()
        
        self.assertEqual(order.status, "Completed")
        self.assertEqual(order.payment_id, "payment_123")
        self.assertEqual(order.customer_email, "customer@test.com")
        self.assertEqual(order.fee, 3.00)

    def test_mark_as_failed(self):
        """Test marking order as failed"""
        order = frappe.get_doc({
            "doctype": "Yoco Order",
            "order_id": "test_failed_order",
            "amount": 100.00,
            "currency": "ZAR",
            "status": "Pending"
        })
        order.insert()
        
        order.mark_as_failed("Test error message")
        order.reload()
        
        self.assertEqual(order.status, "Failed")
        meta_data = json.loads(order.meta_data)
        self.assertEqual(meta_data["error_message"], "Test error message")

    def tearDown(self):
        """Clean up test data"""
        # Clean up test orders
        frappe.db.delete("Yoco Order", {"order_id": ["like", "test_%"]})
        frappe.db.commit()


if __name__ == "__main__":
    unittest.main()