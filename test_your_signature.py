#!/usr/bin/env python3
"""
Ready-to-use script to test YOUR actual PayFast signature.
Run in bench console: bench execute payments.test_your_signature.run_test
"""

def run_test():
    from payments.payment_gateways.payfast_signature_diagnostic import diagnose_signature
    
    # YOUR ACTUAL PAYMENT DATA from Error Log (12)
    result = diagnose_signature(
        form_data={
            'amount': '1450.00',
            'cancel_url': 'https://graduation-ranked-absorption-stickers.trycloudflare.com/api/method/payments.payment_gateways.payfast_itn.handle_itn',
            'custom_str1': '2hdr07ath7',
            'custom_str2': 'ACC-PRQ-2025-00014',
            'email_address': 'christiaan.swart.private@gmail.com',
            'item_description': 'Payment Request for SAL-ORD-2025-00005',
            'item_name': 'Cohenix',
            'm_payment_id': '6k37dc5asp',
            'merchant_id': '10040154',
            'merchant_key': 'n8l3mgmv2rzbx',
            'name_first': 'Christiaan',
            'name_last': 'Swart',
            'notify_url': 'https://graduation-ranked-absorption-stickers.trycloudflare.com/api/method/payments.payment_gateways.payfast_itn.handle_itn',
            'return_url': 'https://graduation-ranked-absorption-stickers.trycloudflare.com/api/method/payments.payment_gateways.payfast_itn.handle_itn'
        },
        passphrase="testmetwicemore"
    )
    
    print("\n" + "="*80)
    print("YOUR ACTUAL PAYFAST SIGNATURE TEST")
    print("="*80)
    
    print(f"\n✓ Generated Signature: {result['report']['output']['final_signature']}")
    print(f"✓ From Your Logs:      baea9a646bf20e7b7776d2128bc56c30")
    print(f"✓ Signatures Match:    {result['report']['output']['final_signature'] == 'baea9a646bf20e7b7776d2128bc56c30'}")
    
    print("\n" + "="*80)
    print("STRING BEING HASHED (first 200 chars):")
    print("="*80)
    print(result['report']['output']['string_to_hash'][:200] + "...")
    
    print("\n" + "="*80)
    print("VALIDATION ISSUES:")
    print("="*80)
    if result['report']['validation']['issues']:
        for issue in result['report']['validation']['issues']:
            print(f"  [{issue['severity'].upper()}] {issue['message']}")
    else:
        print("  ✓ No issues found")
    
    print("\n" + "="*80)
    print("CONCLUSION:")
    print("="*80)
    if result['report']['output']['final_signature'] == 'baea9a646bf20e7b7776d2128bc56c30':
        print("  ✓ Your signature generation is CORRECT!")
        print("  ✓ The code matches your error logs")
        print("\n  The PayFast rejection must be because:")
        print("    → Passphrase in PayFast dashboard ≠ 'testmetwicemore'")
        print("    → OR merchant credentials are different")
        print("    → OR PayFast is receiving modified data")
    
    print("\n" + "="*80)
    print("NEXT STEP:")
    print("="*80)
    print("  1. Log into PayFast dashboard")
    print("  2. Go to Settings → Integration → Security")
    print("  3. Verify passphrase is EXACTLY: testmetwicemore")
    print("  4. Check merchant_id: 10040154")
    print("  5. Check merchant_key: n8l3mgmv2rzbx")
    print("="*80 + "\n")
    
    return result

if __name__ == "__main__":
    run_test()