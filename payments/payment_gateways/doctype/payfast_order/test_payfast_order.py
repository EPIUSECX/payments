# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPayfastOrder(FrappeTestCase):
    def setUp(self):
        """Set up test data"""
        # Create test PayfastSettings if not exists
        if not frappe.db.exists("Payfast Settings", "Test PayFast"):
            payfast_settings = frappe.get_doc({
                "doctype": "Payfast Settings", 
                "name": "Test PayFast",
                "merchant_id": "10000100",
                "merchant_key": "46f0cd694581a",
                "passphrase": "test_passphrase",
                "sandbox_mode": 1
            })
            payfast_settings.insert(ignore_permissions=True)

        # Create test customer if not exists
        if not frappe.db.exists("Customer", "Test Customer PayFast"):
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "Test Customer PayFast",
                "customer_type": "Individual",
                "customer_group": "All Customer Groups",
                "territory": "All Territories"
            })
            customer.insert(ignore_permissions=True)

    def test_payfast_order_creation(self):
        """Test PayFastOrder document creation"""
        order_data = frappe.get_doc({
            "doctype": "PayFast Order",
            "m_payment_id": "test_payment_123",
            "amount_gross": 100.00,
            "currency": "ZAR",
            "status": "Pending"
        })
        order_data.insert()
        
        # Test that order was created with correct values
        self.assertEqual(order_data.status, "Pending")
        self.assertEqual(order_data.amount_gross, 100.00)
        self.assertEqual(order_data.currency, "ZAR")
        self.assertTrue(order_data.name)

    def test_payfast_order_static_creation(self):
        """Test PayFastOrder static creation method"""
        from payments.payment_gateways.doctype.payfast_order.payfast_order import PayfastOrder
        
        result = PayfastOrder.create_order(
            m_payment_id="integration_req_test_001",
            amount_gross=250.00,
            currency="ZAR",
            item_name="Test Payment",
            ref_dt="Payment Request",
            ref_dn="TEST-PR-002"
        )
        
        # Verify result structure
        self.assertIn("payfast_order", result)
        self.assertEqual(result["m_payment_id"], "integration_req_test_001")
        self.assertEqual(result["amount_gross"], 250.00)
        self.assertEqual(result["currency"], "ZAR")
        
        # Verify order was created in database
        order = frappe.get_doc("PayFast Order", result["payfast_order"])
        self.assertEqual(order.amount_gross, 250.00)
        self.assertEqual(order.ref_dt, "Payment Request")
        self.assertEqual(order.ref_dn, "TEST-PR-002")

    def test_itn_signature_verification(self):
        """Test PayFast ITN signature verification"""
        order = frappe.get_doc({
            "doctype": "PayFast Order",
            "m_payment_id": "test_itn_signature",
            "amount_gross": 100.00,
            "currency": "ZAR"
        })
        order.insert()
        
        # Test ITN data with valid signature
        itn_data = {
            "m_payment_id": "test_itn_signature",
            "pf_payment_id": "12345",
            "payment_status": "COMPLETE",
            "item_name": "Test Item",
            "amount_gross": "100.00",
            "amount_fee": "2.30",
            "amount_net": "97.70"
        }
        
        # Generate test signature (this would be done by PayFast in reality)
        from urllib.parse import quote_plus
        import hashlib
        
        settings = frappe.get_single("Payfast Settings")
        passphrase = "test_passphrase"  # Known test passphrase
        
        # Create signature
        sorted_data = sorted(itn_data.items())
        data_string = "&".join([f"{k}={quote_plus(str(v))}" for k, v in sorted_data])
        data_string += f"&passphrase={passphrase}"
        signature = hashlib.md5(data_string.encode("utf-8")).hexdigest()
        
        itn_data["signature"] = signature
        
        # Test signature verification
        self.assertTrue(order.verify_itn_signature(itn_data.copy()))
        
        # Test invalid signature
        itn_data["signature"] = "invalid_signature"
        self.assertFalse(order.verify_itn_signature(itn_data.copy()))

    def test_itn_notification_handling(self):
        """Test ITN notification handling"""
        # Create test order
        order = frappe.get_doc({
            "doctype": "PayFast Order",
            "m_payment_id": "test_itn_handling",
            "amount_gross": 200.00,
            "currency": "ZAR",
            "status": "Pending"
        })
        order.insert()
        
        # Test successful ITN with proper signature
        itn_data = {
            "m_payment_id": "test_itn_handling",
            "pf_payment_id": "67890",
            "payment_status": "COMPLETE",
            "merchant_id": "10000100",
            "amount_gross": "200.00",
            "amount_fee": "4.60",
            "amount_net": "195.40",
            "name_first": "John",
            "name_last": "Doe",
            "email_address": "john@example.com",
            "payment_method": "cc"
        }
        
        # Mock signature verification to return True for testing
        original_verify = order.verify_itn_signature
        order.verify_itn_signature = lambda data: True
        
        try:
            success = order.handle_itn_notification(itn_data)
            order.reload()
            
            # Verify order was updated
            self.assertTrue(success)
            self.assertEqual(order.status, "Complete")
            self.assertEqual(order.pf_payment_id, "67890")
            self.assertEqual(order.amount_fee, 4.60)
            self.assertEqual(order.amount_net, 195.40)
            self.assertEqual(order.name_first, "John")
            self.assertEqual(order.email_address, "john@example.com")
            self.assertTrue(order.signature_verification)
            
        finally:
            # Restore original method
            order.verify_itn_signature = original_verify

    def test_order_status_properties(self):
        """Test order status properties"""
        order = frappe.get_doc({
            "doctype": "PayFast Order",
            "m_payment_id": "test_status_properties",
            "amount_gross": 100.00,
            "currency": "ZAR",
            "status": "Pending"
        })
        order.insert()
        
        # Test initial status
        self.assertFalse(order.is_complete)
        self.assertFalse(order.is_failed)
        self.assertFalse(order.is_cancelled)
        
        # Test complete status
        order.status = "Complete"
        order.save()
        self.assertTrue(order.is_complete)
        
        # Test failed status
        order.status = "Failed"
        order.save()
        self.assertTrue(order.is_failed)
        
        # Test cancelled status
        order.status = "Cancelled"
        order.save()
        self.assertTrue(order.is_cancelled)

    def test_mark_as_complete(self):
        """Test marking order as complete"""
        order = frappe.get_doc({
            "doctype": "PayFast Order",
            "m_payment_id": "test_complete_order",
            "amount_gross": 100.00,
            "currency": "ZAR",
            "status": "Pending"
        })
        order.insert()
        
        itn_data = {
            "pf_payment_id": "complete_123",
            "amount_fee": "2.30",
            "amount_net": "97.70"
        }
        
        order.mark_as_complete(itn_data)
        order.reload()
        
        self.assertEqual(order.status, "Complete")

    def test_mark_as_failed(self):
        """Test marking order as failed"""
        order = frappe.get_doc({
            "doctype": "PayFast Order",
            "m_payment_id": "test_failed_order",
            "amount_gross": 100.00,
            "currency": "ZAR",
            "status": "Pending"
        })
        order.insert()
        
        order.mark_as_failed("Test payment failure")
        order.reload()
        
        self.assertEqual(order.status, "Failed")
        meta_data = json.loads(order.meta_data)
        self.assertEqual(meta_data["error_message"], "Test payment failure")

    def test_validation(self):
        """Test order validation"""
        # Test missing m_payment_id
        with self.assertRaises(frappe.ValidationError):
            order = frappe.get_doc({
                "doctype": "PayFast Order",
                "amount_gross": 100.00,
                "currency": "ZAR"
                # Missing m_payment_id
            })
            order.insert()
        
        # Test invalid amount
        with self.assertRaises(frappe.ValidationError):
            order = frappe.get_doc({
                "doctype": "PayFast Order",
                "m_payment_id": "test_invalid_amount",
                "amount_gross": -50.00,  # Invalid negative amount
                "currency": "ZAR"
            })
            order.insert()
        
        # Test invalid currency
        with self.assertRaises(frappe.ValidationError):
            order = frappe.get_doc({
                "doctype": "PayFast Order",
                "m_payment_id": "test_invalid_currency",
                "amount_gross": 100.00,
                "currency": "USD"  # PayFast only supports ZAR
            })
            order.insert()

    def test_auto_link_integration_request(self):
        """Test auto-linking to Integration Request"""
        # Create test Integration Request
        integration_request = frappe.get_doc({
            "doctype": "Integration Request",
            "name": "test_integration_req_123",
            "integration_request_service": "PayFast",
            "status": "Queued",
            "data": json.dumps({"amount": 100.00, "currency": "ZAR"})
        })
        integration_request.insert(ignore_permissions=True)
        
        # Create order with matching m_payment_id
        order = frappe.get_doc({
            "doctype": "PayFast Order",
            "m_payment_id": "test_integration_req_123",
            "amount_gross": 100.00,
            "currency": "ZAR",
            "status": "Complete"
        })
        order.insert()
        
        # Verify Integration Request was updated
        integration_request.reload()
        self.assertEqual(integration_request.status, "Completed")

    def tearDown(self):
        """Clean up test data"""
        # Clean up test orders
        frappe.db.delete("PayFast Order", {"m_payment_id": ["like", "test_%"]})
        frappe.db.delete("Integration Request", {"name": ["like", "test_%"]})
        frappe.db.commit()


if __name__ == "__main__":
    unittest.main()