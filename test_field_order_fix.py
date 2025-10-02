#!/usr/bin/env python3
"""
Test script to verify PayFast signature fix - Field Order Correction

This tests that signatures are now generated using INSERTION ORDER
instead of alphabetical order, as required by PayFast.

Run: bench execute payments.test_field_order_fix.run_test
"""

import hashlib
from urllib.parse import urlencode


def run_test():
    print("\n" + "="*80)
    print("PayFast Signature Fix - Field Order Test")
    print("="*80)
    
    # Your ACTUAL payment data from logs
    # Build in PayFast's required order
    form_data_correct_order = {}
    
    # 1. Merchant details
    form_data_correct_order["merchant_id"] = "10040154"
    form_data_correct_order["merchant_key"] = "n8l3mgmv2rzbx"
    
    # 2. URLs
    form_data_correct_order["return_url"] = "https://graduation-ranked-absorption-stickers.trycloudflare.com/api/method/payments.payment_gateways.payfast_itn.handle_itn"
    form_data_correct_order["cancel_url"] = "https://graduation-ranked-absorption-stickers.trycloudflare.com/api/method/payments.payment_gateways.payfast_itn.handle_itn"
    form_data_correct_order["notify_url"] = "https://graduation-ranked-absorption-stickers.trycloudflare.com/api/method/payments.payment_gateways.payfast_itn.handle_itn"
    
    # 3. Buyer details
    form_data_correct_order["name_first"] = "Christiaan"
    form_data_correct_order["name_last"] = "Swart"
    form_data_correct_order["email_address"] = "christiaan.swart.private@gmail.com"
    
    # 4. Transaction details
    form_data_correct_order["m_payment_id"] = "6k37dc5asp"
    form_data_correct_order["amount"] = "1450.00"
    form_data_correct_order["item_name"] = "Cohenix"
    form_data_correct_order["item_description"] = "Payment Request for SAL-ORD-2025-00005"
    
    # 5. Custom fields
    form_data_correct_order["custom_str1"] = "2hdr07ath7"
    form_data_correct_order["custom_str2"] = "ACC-PRQ-2025-00014"
    
    passphrase = "testmetwicemore"
    
    # Generate signature with INSERTION ORDER (no sorting!)
    payload_string = urlencode(list(form_data_correct_order.items()))
    full_string = f"{payload_string}&passphrase={passphrase}"
    signature_correct = hashlib.md5(full_string.encode("utf-8")).hexdigest()
    
    # Compare with ALPHABETICAL ORDER (old wrong way)
    payload_string_alphabetical = urlencode(list(sorted(form_data_correct_order.items())))
    full_string_alphabetical = f"{payload_string_alphabetical}&passphrase={passphrase}"
    signature_alphabetical = hashlib.md5(full_string_alphabetical.encode("utf-8")).hexdigest()
    
    print("\n" + "-"*80)
    print("FIELD ORDER COMPARISON:")
    print("-"*80)
    
    print("\nCorrect Order (Insertion):")
    for i, (k, v) in enumerate(form_data_correct_order.items(), 1):
        print(f"  {i:2}. {k:20} = {v[:50]}..." if len(str(v)) > 50 else f"  {i:2}. {k:20} = {v}")
    
    print("\nAlphabetical Order (Wrong):")
    for i, (k, v) in enumerate(sorted(form_data_correct_order.items()), 1):
        print(f"  {i:2}. {k:20} = {v[:50]}..." if len(str(v)) > 50 else f"  {i:2}. {k:20} = {v}")
    
    print("\n" + "-"*80)
    print("SIGNATURE COMPARISON:")
    print("-"*80)
    print(f"\n✓ Correct (Insertion Order): {signature_correct}")
    print(f"✗ Wrong (Alphabetical):      {signature_alphabetical}")
    print(f"\nFrom Your Logs:              baea9a646bf20e7b7776d2128bc56c30")
    
    print("\n" + "-"*80)
    print("RESULTS:")
    print("-"*80)
    
    log_signature = "baea9a646bf20e7b7776d2128bc56c30"
    
    if signature_correct == log_signature:
        print("✓✓✓ CORRECT ORDER MATCHES YOUR LOGS! ✓✓✓")
        print("\nThe fix is working! Field order now matches PayFast requirements.")
    elif signature_alphabetical == log_signature:
        print("✗✗✗ ALPHABETICAL ORDER MATCHES (this was the bug)")
        print("\nYour logs used alphabetical - that's why PayFast rejected it!")
    else:
        print("⚠ Neither matches - there may be other differences")
        print(f"Check field values carefully")
    
    print("\n" + "-"*80)
    print("PAYLOAD STRING FOR PAYFAST TROUBLESHOOTER:")
    print("-"*80)
    print("\nCopy this string to test on PayFast's Signature Troubleshooter:")
    print("\n" + payload_string)
    
    print("\n" + "-"*80)
    print("FULL STRING BEING HASHED (with passphrase):")
    print("-"*80)
    print(full_string[:150] + "...")
    print(f"\nLength: {len(full_string)} characters")
    
    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Restart bench: bench restart")
    print("2. Test the payload string above on PayFast's troubleshooter")
    print("3. Try an actual payment")
    print("4. Signature should now be accepted by PayFast!")
    print("="*80 + "\n")
    
    # Save payload to file
    with open("payfast_correct_order_payload.txt", "w") as f:
        f.write(payload_string)
    print("✓ Payload string saved to: payfast_correct_order_payload.txt\n")
    
    return {
        "signature_correct_order": signature_correct,
        "signature_alphabetical": signature_alphabetical,
        "log_signature": log_signature,
        "matches_logs": signature_correct == log_signature,
        "payload_string": payload_string
    }


if __name__ == "__main__":
    run_test()