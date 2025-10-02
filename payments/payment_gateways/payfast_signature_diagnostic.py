# Copyright (c) 2024, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""
PayFast Signature Diagnostic Tool

This tool helps debug PayFast signature generation issues by providing:
1. Detailed breakdown of signature generation process
2. Step-by-step visibility into data transformation
3. Comparison with PayFast's expected format
4. Test functionality without actual payments

Usage:
    bench execute payments.payment_gateways.payfast_signature_diagnostic.test_signature

Or via API:
    POST /api/method/payments.payment_gateways.payfast_signature_diagnostic.diagnose_signature
    {
        "form_data": {...},
        "passphrase": "testmetwicemore"
    }
"""

import hashlib
import json
from urllib.parse import urlencode, quote_plus

import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def diagnose_signature(form_data=None, passphrase=None):
    """
    Diagnose PayFast signature generation with detailed breakdown.
    
    This whitelisted method allows testing signature generation without making actual payments.
    It shows exactly what string is being hashed and compares with PayFast's expected format.
    
    Args:
        form_data: Dictionary or JSON string of PayFast form data
        passphrase: Optional passphrase for signature generation
        
    Returns:
        dict: Comprehensive diagnostic information
    """
    try:
        # Parse form_data if it's a string
        if isinstance(form_data, str):
            form_data = json.loads(form_data)
        
        if not form_data:
            return {
                "success": False,
                "error": "form_data is required"
            }
        
        # Generate diagnostic report
        report = generate_diagnostic_report(form_data, passphrase)
        
        return {
            "success": True,
            "report": report
        }
        
    except Exception as e:
        frappe.log_error(
            f"Error in diagnose_signature: {str(e)}\n{frappe.get_traceback()}",
            "PayFast Signature Diagnostic Error"
        )
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }


def generate_diagnostic_report(form_data, passphrase=None):
    """
    Generate comprehensive diagnostic report for signature generation.
    
    Args:
        form_data: Dictionary of PayFast form data
        passphrase: Optional passphrase
        
    Returns:
        dict: Detailed diagnostic information
    """
    report = {
        "timestamp": frappe.utils.now(),
        "input": {},
        "processing": {},
        "output": {},
        "validation": {},
        "recommendations": []
    }
    
    # 1. INPUT ANALYSIS
    report["input"]["raw_form_data"] = form_data.copy()
    report["input"]["passphrase_provided"] = bool(passphrase)
    report["input"]["passphrase_length"] = len(passphrase) if passphrase else 0
    report["input"]["form_data_keys"] = sorted(form_data.keys())
    report["input"]["form_data_count"] = len(form_data)
    
    # Check for signature in input (should be excluded)
    if "signature" in form_data:
        report["input"]["warning"] = "signature field found in input (will be excluded)"
    
    # 2. PROCESSING STEPS
    
    # Step 1: Remove signature field
    signature_data = {k: v for k, v in form_data.items() if k != "signature"}
    report["processing"]["step_1_remove_signature"] = {
        "description": "Remove signature field from data",
        "result": signature_data.copy(),
        "keys_after": sorted(signature_data.keys())
    }
    
    # Step 2: Sort items
    sorted_items = sorted(signature_data.items())
    report["processing"]["step_2_sort_items"] = {
        "description": "Sort items alphabetically by key",
        "result": sorted_items,
        "order": [k for k, v in sorted_items]
    }
    
    # Step 3: URL encode (standard urlencode)
    encoded_string = urlencode(sorted_items)
    report["processing"]["step_3_url_encode"] = {
        "description": "URL encode using standard urlencode()",
        "result": encoded_string,
        "length": len(encoded_string)
    }
    
    # Step 4: Add passphrase (if provided)
    if passphrase:
        string_with_passphrase = f"{encoded_string}&passphrase={passphrase}"
        report["processing"]["step_4_add_passphrase"] = {
            "description": "Add passphrase (NOT URL encoded)",
            "passphrase_value": passphrase,
            "result": string_with_passphrase,
            "length": len(string_with_passphrase)
        }
        final_string = string_with_passphrase
    else:
        report["processing"]["step_4_add_passphrase"] = {
            "description": "No passphrase provided - skipped",
            "result": encoded_string
        }
        final_string = encoded_string
    
    # Step 5: Generate MD5 hash
    signature = hashlib.md5(final_string.encode("utf-8")).hexdigest()
    report["processing"]["step_5_generate_md5"] = {
        "description": "Generate MD5 hash of final string",
        "input_string": final_string,
        "input_bytes": final_string.encode("utf-8").hex(),
        "signature": signature
    }
    
    # 3. OUTPUT
    report["output"]["final_signature"] = signature
    report["output"]["string_to_hash"] = final_string
    report["output"]["string_length"] = len(final_string)
    
    # 4. VALIDATION CHECKS
    
    # Check for common issues
    validation_issues = []
    
    # Check for empty values
    empty_values = [k for k, v in signature_data.items() if not v]
    if empty_values:
        validation_issues.append({
            "type": "empty_values",
            "severity": "warning",
            "message": f"Empty values found for keys: {', '.join(empty_values)}",
            "recommendation": "PayFast may reject empty values. Consider removing empty fields."
        })
    
    # Check for special characters
    special_char_keys = []
    for k, v in signature_data.items():
        if isinstance(v, str) and any(c in v for c in ['&', '=', '%', '+', ' ']):
            special_char_keys.append(k)
    
    if special_char_keys:
        validation_issues.append({
            "type": "special_characters",
            "severity": "info",
            "message": f"Special characters found in: {', '.join(special_char_keys)}",
            "recommendation": "These will be URL encoded by urlencode()"
        })
    
    # Check passphrase
    if passphrase:
        if len(passphrase) < 8:
            validation_issues.append({
                "type": "passphrase_length",
                "severity": "warning",
                "message": "Passphrase is shorter than 8 characters",
                "recommendation": "PayFast recommends passphrases of at least 8 characters"
            })
        
        # Check if passphrase matches known test value
        if passphrase == "testmetwicemore":
            validation_issues.append({
                "type": "passphrase_match",
                "severity": "info",
                "message": "Using known test passphrase: testmetwicemore",
                "recommendation": "Ensure this matches your PayFast dashboard settings"
            })
    else:
        validation_issues.append({
            "type": "no_passphrase",
            "severity": "warning",
            "message": "No passphrase provided",
            "recommendation": "If you have a passphrase set in PayFast dashboard, you must include it"
        })
    
    # Check for required fields
    required_fields = ["merchant_id", "merchant_key", "amount", "item_name"]
    missing_fields = [f for f in required_fields if f not in signature_data]
    if missing_fields:
        validation_issues.append({
            "type": "missing_required_fields",
            "severity": "error",
            "message": f"Missing required fields: {', '.join(missing_fields)}",
            "recommendation": "These fields are required by PayFast"
        })
    
    report["validation"]["issues"] = validation_issues
    report["validation"]["issue_count"] = len(validation_issues)
    
    # 5. ALTERNATIVE ENCODING METHODS (for comparison)
    report["alternatives"] = {}
    
    # Try quote_plus encoding
    try:
        quote_plus_items = "&".join([f"{k}={quote_plus(str(v))}" for k, v in sorted_items])
        quote_plus_sig = hashlib.md5(
            (quote_plus_items + (f"&passphrase={passphrase}" if passphrase else "")).encode("utf-8")
        ).hexdigest()
        report["alternatives"]["quote_plus_encoding"] = {
            "description": "Using quote_plus instead of urlencode",
            "encoded_string": quote_plus_items,
            "signature": quote_plus_sig,
            "matches_main": quote_plus_sig == signature
        }
    except Exception as e:
        report["alternatives"]["quote_plus_encoding"] = {"error": str(e)}
    
    # Try without sorting
    try:
        unsorted_string = urlencode(signature_data.items())
        unsorted_sig = hashlib.md5(
            (unsorted_string + (f"&passphrase={passphrase}" if passphrase else "")).encode("utf-8")
        ).hexdigest()
        report["alternatives"]["unsorted_encoding"] = {
            "description": "Without sorting items",
            "encoded_string": unsorted_string,
            "signature": unsorted_sig,
            "matches_main": unsorted_sig == signature
        }
    except Exception as e:
        report["alternatives"]["unsorted_encoding"] = {"error": str(e)}
    
    # 6. RECOMMENDATIONS
    recommendations = []
    
    recommendations.append("✓ Using urlencode() with sorted items (correct per PayFast docs)")
    recommendations.append("✓ Passphrase appended without URL encoding (correct per PayFast docs)")
    recommendations.append("✓ Using MD5 hash (correct per PayFast docs)")
    
    if not passphrase:
        recommendations.append("⚠ Add passphrase if configured in PayFast dashboard")
    
    if empty_values:
        recommendations.append("⚠ Consider removing empty form fields before signing")
    
    recommendations.append("💡 Compare 'final_signature' with PayFast's expected signature")
    recommendations.append("💡 Verify passphrase matches exactly in PayFast dashboard")
    recommendations.append("💡 Check that all form field values are strings (not numbers)")
    
    report["recommendations"] = recommendations
    
    return report


def test_signature_with_sample_data():
    """
    Test signature generation with sample PayFast data.
    
    This can be called from bench console:
        bench execute payments.payment_gateways.payfast_signature_diagnostic.test_signature_with_sample_data
    """
    print("\n" + "="*80)
    print("PayFast Signature Diagnostic Test")
    print("="*80 + "\n")
    
    # Sample data based on PayFast documentation
    sample_data = {
        "merchant_id": "10000100",
        "merchant_key": "46f0cd694581a",
        "amount": "100.00",
        "item_name": "Test Product",
        "return_url": "https://example.com/return",
        "cancel_url": "https://example.com/cancel",
        "notify_url": "https://example.com/notify"
    }
    
    passphrase = "testmetwicemore"
    
    print("Sample Form Data:")
    print(json.dumps(sample_data, indent=2))
    print(f"\nPassphrase: {passphrase}")
    print("\n" + "-"*80 + "\n")
    
    # Generate report
    report = generate_diagnostic_report(sample_data, passphrase)
    
    # Print key information
    print("SIGNATURE GENERATION PROCESS:")
    print("-"*80)
    
    print("\n1. Input Data (sorted):")
    for k, v in sorted(sample_data.items()):
        print(f"   {k} = {v}")
    
    print(f"\n2. URL Encoded String:")
    print(f"   {report['processing']['step_3_url_encode']['result']}")
    
    print(f"\n3. With Passphrase:")
    print(f"   {report['output']['string_to_hash']}")
    
    print(f"\n4. MD5 Hash (Signature):")
    print(f"   {report['output']['final_signature']}")
    
    print("\n" + "-"*80)
    print("\nVALIDATION ISSUES:")
    if report['validation']['issues']:
        for issue in report['validation']['issues']:
            print(f"   [{issue['severity'].upper()}] {issue['message']}")
    else:
        print("   No issues found")
    
    print("\n" + "-"*80)
    print("\nRECOMMENDATIONS:")
    for rec in report['recommendations']:
        print(f"   {rec}")
    
    print("\n" + "="*80)
    print("Full diagnostic report saved to: payfast_diagnostic_report.json")
    print("="*80 + "\n")
    
    # Save full report
    with open("payfast_diagnostic_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    return report


@frappe.whitelist(allow_guest=False)
def compare_signatures(form_data=None, passphrase=None, expected_signature=None):
    """
    Compare generated signature with expected signature from PayFast.
    
    Args:
        form_data: Form data dictionary or JSON string
        passphrase: Passphrase used
        expected_signature: The signature PayFast expects
        
    Returns:
        dict: Comparison results with detailed analysis
    """
    try:
        if isinstance(form_data, str):
            form_data = json.loads(form_data)
        
        # Generate our signature
        report = generate_diagnostic_report(form_data, passphrase)
        our_signature = report['output']['final_signature']
        
        # Compare
        match = our_signature == expected_signature if expected_signature else None
        
        result = {
            "success": True,
            "comparison": {
                "our_signature": our_signature,
                "expected_signature": expected_signature,
                "match": match,
                "string_we_hashed": report['output']['string_to_hash']
            },
            "full_report": report
        }
        
        if not match and expected_signature:
            # Try to identify differences
            result["analysis"] = analyze_signature_mismatch(
                form_data, passphrase, our_signature, expected_signature
            )
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }


def analyze_signature_mismatch(form_data, passphrase, our_sig, expected_sig):
    """
    Analyze why signatures don't match and suggest fixes.
    
    Args:
        form_data: Form data
        passphrase: Passphrase
        our_sig: Our generated signature
        expected_sig: PayFast's expected signature
        
    Returns:
        dict: Analysis of potential issues
    """
    analysis = {
        "potential_issues": [],
        "things_to_check": []
    }
    
    # Check if passphrase might be wrong
    analysis["things_to_check"].append(
        "Verify passphrase in PayFast dashboard exactly matches: " + (passphrase or "NONE")
    )
    
    # Check for data type issues
    for k, v in form_data.items():
        if not isinstance(v, str):
            analysis["potential_issues"].append(
                f"Field '{k}' is not a string (type: {type(v).__name__}). Convert to string."
            )
    
    # Check for encoding issues
    analysis["things_to_check"].append(
        "Ensure all field values use UTF-8 encoding"
    )
    
    analysis["things_to_check"].append(
        "Check if PayFast dashboard has any special characters in merchant_key"
    )
    
    analysis["things_to_check"].append(
        "Verify you're using the correct merchant_id and merchant_key for your environment (sandbox vs live)"
    )
    
    # Try variations
    analysis["signature_variations"] = {}
    
    # Try with different passphrase positions
    try:
        signature_data = {k: v for k, v in form_data.items() if k != "signature"}
        encoded = urlencode(sorted(signature_data.items()))
        
        # Passphrase URL encoded
        if passphrase:
            from urllib.parse import quote
            encoded_pass = f"{encoded}&passphrase={quote(passphrase)}"
            sig_with_encoded_pass = hashlib.md5(encoded_pass.encode("utf-8")).hexdigest()
            analysis["signature_variations"]["with_url_encoded_passphrase"] = {
                "signature": sig_with_encoded_pass,
                "matches": sig_with_encoded_pass == expected_sig,
                "string_hashed": encoded_pass
            }
    except:
        pass
    
    return analysis


# Quick test function
def test_signature():
    """
    Quick test function - can be called from bench console.
    
    Usage:
        bench execute payments.payment_gateways.payfast_signature_diagnostic.test_signature
    """
    return test_signature_with_sample_data()