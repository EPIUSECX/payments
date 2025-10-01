# PayFast Checkout Timeout - Debugging Guide

**Issue:** Timeout when accessing `/payfast_checkout?token=...`

## How to Check Logs

1. **Access Frappe Error Log:**
   ```
   Navigate to: Home → Tools → Error Log
   OR
   Direct URL: https://your-site.com/app/error-log
   ```

2. **Filter for PayFast Debug logs:**
   - Look for titles starting with `[PAYFAST DEBUG]`
   - Check timestamps to see where it hangs
   - Note the timing for each step

3. **What to Look For:**
   - Which step takes longest?
   - Any error messages?
   - Does it complete all steps or stop somewhere?

## Expected Log Sequence

### When you access `/payfast_checkout?token=XXX`:
```
[PAYFAST DEBUG] get_context started
[PAYFAST DEBUG] Step 1: Validating token
[PAYFAST DEBUG] Step 1 complete in X.XXs
[PAYFAST DEBUG] Step 2: Getting Integration Request  
[PAYFAST DEBUG] Step 2 complete in X.XXs
[PAYFAST DEBUG] Step 3: Parsing payment details
[PAYFAST DEBUG] Step 3 complete in X.XXs
[PAYFAST DEBUG] Step 4: Setting context keys
[PAYFAST DEBUG] Step 4 complete in X.XXs
[PAYFAST DEBUG] Step 5: Getting Payment Gateway
[PAYFAST DEBUG] Step 5 complete in X.XXs
[PAYFAST DEBUG] get_context completed successfully in X.XXs
```

### When you click "Pay with Payfast" button:
```
[PAYFAST DEBUG] get_payment_url called with token: XXX
[PAYFAST DEBUG] Step 1: Getting Integration Request
[PAYFAST DEBUG] Step 1 complete in X.XXs
[PAYFAST DEBUG] Step 2: Parsing payment details
[PAYFAST DEBUG] Step 2 complete in X.XXs
[PAYFAST DEBUG] Step 3: Getting Payfast Settings
[PAYFAST DEBUG] Step 3 complete in X.XXs
[PAYFAST DEBUG] Step 4: Calling controller.get_payment_url()
  └─> [PAYFAST DEBUG] get_payment_url called on settings
  └─> [PAYFAST DEBUG] Creating Integration Request
  └─> [PAYFAST DEBUG] Integration Request created
  └─> [PAYFAST DEBUG] get_payment_url completed
[PAYFAST DEBUG] Step 4 complete in X.XXs
[PAYFAST DEBUG] get_payment_url completed in X.XXs
```

## Diagnosis Scenarios

### Scenario A: Hangs on "Step 3: Getting Payfast Settings"
**Likely Cause:** PayFast Settings document doesn't exist or name is wrong  
**Action:** Check if PayFast Settings document exists

### Scenario B: Hangs on "Creating Integration Request"
**Likely Cause:** Database slow or Integration Request doctype issue  
**Action:** Check database performance

### Scenario C: Hangs on "Importing PayFastOrder class"
**Likely Cause:** Import errors in new payfast_utils.py or payfast_constants.py  
**Action:** Check Python import errors

### Scenario D: Hangs after "get_payment_url completed"
**Likely Cause:** Wrong return value - creating circular redirect  
**Action:** Check get_payment_url() logic

## Next Steps After Checking Logs

1. Note which step hangs
2. Share the error log entries
3. I'll provide the specific fix

## Common Issues

### Import Error
If you see "ModuleNotFoundError" or "ImportError":
```bash
# Restart Frappe bench
bench restart
```

### Missing requests library
If logs mention "requests" module:
```bash
pip install requests
# OR
bench pip install requests
```

### Wrong flow in get_payment_url()
If it creates duplicate Integration Requests, we need to refactor the method.