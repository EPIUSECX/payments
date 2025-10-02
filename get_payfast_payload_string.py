#!/usr/bin/env python3
"""
Generate the exact payload string to test with PayFast's Signature Troubleshooter.
Run: bench execute payments.get_payfast_payload_string.run
"""

def run():
    from urllib.parse import urlencode
    
    # Your EXACT payment data from Error Log (12)
    form_data = {
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
    }
    
    # Generate payload string (WITHOUT passphrase - PayFast adds it)
    payload_string = urlencode(sorted(form_data.items()))
    
    print("\n" + "="*80)
    print("PAYLOAD STRING FOR PAYFAST SIGNATURE TROUBLESHOOTER")
    print("="*80)
    print("\n1. Copy the string below (everything between the lines):")
    print("-"*80)
    print(payload_string)
    print("-"*80)
    
    print("\n2. Paste it into PayFast's 'Payload String' field")
    print("   URL: https://sandbox.payfast.co.za/eng/process (scroll down)")
    
    print("\n3. Click 'Test signature matching'")
    
    print("\n4. PayFast will show:")
    print("   - Their generated signature")
    print("   - Whether it matches yours")
    
    print("\n" + "="*80)
    print("YOUR SIGNATURE (from logs):")
    print("="*80)
    print("baea9a646bf20e7b7776d2128bc56c30")
    
    print("\n" + "="*80)
    print("WHAT TO CHECK:")
    print("="*80)
    print("✓ If PayFast generates the SAME signature:")
    print("  → Your code is correct!")
    print("  → Problem is elsewhere (merchant ID, passphrase, etc.)")
    print("\n✗ If PayFast generates a DIFFERENT signature:")
    print("  → PayFast will show what's wrong")
    print("  → Follow their recommendations")
    
    print("\n" + "="*80)
    print("NOTE: Your passphrase is 'testmetwicemore'")
    print("Make sure PayFast dashboard has the same passphrase configured!")
    print("="*80 + "\n")
    
    # Also save to file for easy copy-paste
    with open("payfast_payload_string.txt", "w") as f:
        f.write(payload_string)
    
    print("✓ Payload string also saved to: payfast_payload_string.txt\n")
    
    return payload_string

if __name__ == "__main__":
    run()