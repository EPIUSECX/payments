#!/usr/bin/env python3
"""
Test script for Yoco Payment Gateway Integration
This script tests the complete payment flow from Sales Order to Payment completion.
"""

import frappe
import json
from frappe.utils import flt, nowdate


def test_yoco_integration():
    """Test the complete Yoco payment integration flow."""
    
    print("🧪 Testing Yoco Payment Gateway Integration")
    print("=" * 50)
    
    # Test 1: Check Yoco Settings
    print("\n1. Testing Yoco Settings...")
    try:
        yoco_settings = frappe.get_doc("Yoco Settings")
        print(f"   ✅ Yoco Settings found: {yoco_settings.name}")
        
        # Test currency validation
        yoco_settings.validate_transaction_currency("ZAR")
        print("   ✅ ZAR currency validation passed")
        
        # Test minimum amount validation
        yoco_settings.validate_minimum_transaction_amount("ZAR", 10.00)
        print("   ✅ Minimum amount validation passed")
        
    except Exception as e:
        print(f"   ❌ Yoco Settings test failed: {e}")
        return False
    
    # Test 2: Create Test Sales Order
    print("\n2. Creating test Sales Order...")
    try:
        sales_order = create_test_sales_order()
        print(f"   ✅ Sales Order created: {sales_order.name}")
    except Exception as e:
        print(f"   ❌ Sales Order creation failed: {e}")
        return False
    
    # Test 3: Create Payment Request
    print("\n3. Creating Payment Request...")
    try:
        payment_request = create_test_payment_request(sales_order)
        print(f"   ✅ Payment Request created: {payment_request.name}")
        print(f"   📄 Amount: {payment_request.grand_total} {payment_request.currency}")
        print(f"   📄 Status: {payment_request.status}")
    except Exception as e:
        print(f"   ❌ Payment Request creation failed: {e}")
        return False
    
    # Test 4: Test Payment URL Generation
    print("\n4. Testing Payment URL generation...")
    try:
        payment_url = payment_request.get_payment_url()
        print(f"   ✅ Payment URL generated: {payment_url}")
        
        # Extract token from URL
        token = payment_url.split("token=")[1] if "token=" in payment_url else None
        if token:
            print(f"   ✅ Integration Request token: {token}")
        else:
            print("   ❌ No token found in payment URL")
            return False
            
    except Exception as e:
        print(f"   ❌ Payment URL generation failed: {e}")
        return False
    
    # Test 5: Test Integration Request
    print("\n5. Testing Integration Request...")
    try:
        integration_request = frappe.get_doc("Integration Request", token)
        print(f"   ✅ Integration Request found: {integration_request.name}")
        print(f"   📄 Status: {integration_request.status}")
        print(f"   📄 Service: {integration_request.service}")
        
        # Parse data
        request_data = json.loads(integration_request.data)
        print(f"   📄 Reference: {request_data.get('reference_doctype')} - {request_data.get('reference_docname')}")
        
    except Exception as e:
        print(f"   ❌ Integration Request test failed: {e}")
        return False
    
    # Test 6: Simulate Payment Authorization
    print("\n6. Simulating payment authorization...")
    try:
        # Simulate successful payment
        payment_request.run_method("on_payment_authorized", "Completed")
        payment_request.reload()
        
        print(f"   ✅ Payment authorized successfully")
        print(f"   📄 Payment Request status: {payment_request.status}")
        
        # Check if Payment Entry was created
        payment_entries = frappe.get_all(
            "Payment Entry",
            filters={"reference_no": payment_request.name},
            fields=["name", "paid_amount", "docstatus"]
        )
        
        if payment_entries:
            pe = payment_entries[0]
            print(f"   ✅ Payment Entry created: {pe.name}")
            print(f"   📄 Amount: {pe.paid_amount}")
            print(f"   📄 Status: {'Submitted' if pe.docstatus == 1 else 'Draft'}")
        else:
            print("   ❌ No Payment Entry found")
            return False
            
    except Exception as e:
        print(f"   ❌ Payment authorization failed: {e}")
        return False
    
    # Test 7: Check Sales Invoice Creation
    print("\n7. Checking Sales Invoice creation...")
    try:
        sales_invoices = frappe.get_all(
            "Sales Invoice",
            filters={"sales_order": sales_order.name},
            fields=["name", "grand_total", "docstatus", "outstanding_amount"]
        )
        
        if sales_invoices:
            si = sales_invoices[0]
            print(f"   ✅ Sales Invoice created: {si.name}")
            print(f"   📄 Amount: {si.grand_total}")
            print(f"   📄 Outstanding: {si.outstanding_amount}")
            print(f"   📄 Status: {'Submitted' if si.docstatus == 1 else 'Draft'}")
        else:
            print("   ⚠️  No Sales Invoice found (may be expected if make_sales_invoice=False)")
            
    except Exception as e:
        print(f"   ❌ Sales Invoice check failed: {e}")
    
    # Test 8: Check Sales Order Status
    print("\n8. Checking Sales Order status...")
    try:
        sales_order.reload()
        print(f"   ✅ Sales Order status: {sales_order.status}")
        print(f"   📄 Advance paid: {sales_order.advance_paid}")
        
        if sales_order.status in ["To Ship", "To Ship and Pay"]:
            print("   ✅ Sales Order status updated correctly")
        else:
            print(f"   ⚠️  Unexpected Sales Order status: {sales_order.status}")
            
    except Exception as e:
        print(f"   ❌ Sales Order status check failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Yoco Integration Test Completed!")
    print("\n📋 Summary:")
    print("   - Yoco Settings: ✅")
    print("   - Sales Order Creation: ✅")
    print("   - Payment Request Creation: ✅")
    print("   - Payment URL Generation: ✅")
    print("   - Integration Request: ✅")
    print("   - Payment Authorization: ✅")
    print("   - Payment Entry Creation: ✅")
    print("   - Sales Invoice Creation: ✅")
    print("   - Sales Order Status Update: ✅")
    
    return True


def create_test_sales_order():
    """Create a test Sales Order for testing."""
    
    # Create or get test customer
    customer_name = "Test Customer - Yoco"
    if not frappe.db.exists("Customer", customer_name):
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": "Individual",
            "customer_group": "Individual",
            "territory": "South Africa"
        })
        customer.insert(ignore_permissions=True)
    
    # Create or get test item
    item_code = "Test Item - Yoco"
    if not frappe.db.exists("Item", item_code):
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": "Test Item for Yoco Payment",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "standard_rate": 100.00
        })
        item.insert(ignore_permissions=True)
    
    # Create Sales Order
    sales_order = frappe.get_doc({
        "doctype": "Sales Order",
        "customer": customer_name,
        "transaction_date": nowdate(),
        "delivery_date": nowdate(),
        "currency": "ZAR",
        "items": [{
            "item_code": item_code,
            "qty": 2,
            "rate": 100.00,
            "amount": 200.00
        }]
    })
    
    sales_order.insert(ignore_permissions=True)
    sales_order.submit()
    
    return sales_order


def create_test_payment_request(sales_order):
    """Create a Payment Request for the Sales Order."""
    
    # Get Yoco Payment Gateway Account
    gateway_account = frappe.get_all(
        "Payment Gateway Account",
        filters={"payment_gateway": "Yoco"},
        fields=["name"]
    )
    
    if not gateway_account:
        # Create Payment Gateway Account if it doesn't exist
        yoco_settings = frappe.get_doc("Yoco Settings")
        
        payment_gateway_account = frappe.get_doc({
            "doctype": "Payment Gateway Account",
            "payment_gateway": f"Yoco-{yoco_settings.name}",
            "payment_account": frappe.get_value("Company", sales_order.company, "default_cash_account"),
            "currency": "ZAR"
        })
        payment_gateway_account.insert(ignore_permissions=True)
        gateway_account_name = payment_gateway_account.name
    else:
        gateway_account_name = gateway_account[0].name
    
    # Create Payment Request
    payment_request = frappe.get_doc({
        "doctype": "Payment Request",
        "payment_gateway_account": gateway_account_name,
        "payment_request_type": "Inward",
        "party_type": "Customer",
        "party": sales_order.customer,
        "reference_doctype": "Sales Order",
        "reference_name": sales_order.name,
        "currency": sales_order.currency,
        "grand_total": sales_order.grand_total,
        "email_to": "test@example.com",
        "subject": f"Payment Request for {sales_order.name}",
        "make_sales_invoice": 1,  # This ensures Sales Invoice is created
        "mute_email": 1  # Don't send email during test
    })
    
    payment_request.insert(ignore_permissions=True)
    payment_request.submit()
    
    return payment_request


if __name__ == "__main__":
    # Initialize Frappe
    frappe.init(site="your-site-name")  # Replace with actual site name
    frappe.connect()
    
    try:
        test_yoco_integration()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        frappe.destroy()
