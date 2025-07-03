# Apple Pay Setup Guide for Yoco Payment Gateway

## 🍎 Apple Pay Configuration

I've added Apple Pay support to the Yoco payment gateway. Here's how to set it up:

### 1. **Updated Files**

The following files have been modified to support Apple Pay:

- ✅ `yoco_settings.json` - Added Apple Pay configuration fields
- ✅ `yoco_checkout.py` - Added Apple Pay config retrieval
- ✅ `yoco_checkout.js` - Added conditional Apple Pay inclusion

### 2. **New Configuration Fields**

In **Yoco Settings**, you'll now see:

```
Apple Pay Configuration
├── Enable Apple Pay ☑️ (checked by default)
└── Apple Pay Merchant ID (text field)
```

### 3. **How Apple Pay Works**

The JavaScript now:
1. **Conditionally includes Apple Pay** in payment methods only if:
   - `Enable Apple Pay` is checked ✅
   - `Apple Pay Merchant ID` is configured 📝
2. **Adds Apple Pay configuration** with proper merchant identifier
3. **Supports all major card networks** (Visa, MasterCard, Amex, Discover)

## 🔧 Setup Steps

### Step 1: Configure Yoco Settings
1. Go to **Payment Gateway > Yoco Settings**
2. Check **Enable Apple Pay** ✅
3. Enter your **Apple Pay Merchant ID** (e.g., `merchant.com.yourcompany.yoco`)

### Step 2: Apple Pay Requirements

For Apple Pay to appear as a payment option, **ALL** of these must be met:

#### **Device & Browser Requirements**
- ✅ **Safari** on macOS, iOS, or iPadOS
- ✅ **Chrome/Edge** on macOS (with Apple Pay enabled)
- ✅ Device with **Touch ID**, **Face ID**, or **Apple Watch** paired

#### **Technical Requirements**
- ✅ **HTTPS only** - Apple Pay doesn't work on HTTP
- ✅ **Domain verification** with Apple (through Apple Developer account)
- ✅ **Yoco merchant account** approved for Apple Pay

### Step 3: Apple Developer Setup

1. **Apple Developer Account**:
   - Sign up at [developer.apple.com](https://developer.apple.com)
   - Create a Merchant ID (e.g., `merchant.com.yourcompany.yoco`)

2. **Domain Verification**:
   - Add your domain to Apple Pay merchant settings
   - Upload domain verification file to your website

3. **Yoco Configuration**:
   - Contact Yoco support to enable Apple Pay for your merchant account
   - Provide your Apple Merchant ID to Yoco

## 🧪 Testing Apple Pay

### Test Environment
1. Use **Yoco sandbox mode** ✅
2. Test on **Safari** (macOS/iOS) or **Chrome** (macOS)
3. Ensure your site is served over **HTTPS**

### Expected Behavior

**✅ Apple Pay Available:**
- Payment popup shows: Card, Apple Pay, Google Pay, Instant EFT
- Apple Pay button appears with Apple logo

**❌ Apple Pay Not Available:**
- Payment popup shows: Card, Google Pay, Instant EFT
- No Apple Pay option (this is normal on non-Apple devices/browsers)

## 🔍 Troubleshooting

### Apple Pay Not Showing?

1. **Check Device/Browser**:
   ```
   ❌ Windows/Linux → Apple Pay not supported
   ❌ Firefox/Chrome on Windows → Apple Pay not supported
   ✅ Safari on macOS/iOS → Apple Pay supported
   ✅ Chrome on macOS → Apple Pay supported (if enabled)
   ```

2. **Check HTTPS**:
   ```
   ❌ http://localhost:8000 → Apple Pay not supported
   ✅ https://yoursite.com → Apple Pay supported
   ```

3. **Check Configuration**:
   ```javascript
   // In browser console, check if Apple Pay is available:
   if (window.ApplePaySession && ApplePaySession.canMakePayments()) {
       console.log("Apple Pay is available");
   } else {
       console.log("Apple Pay is not available");
   }
   ```

4. **Check Yoco Settings**:
   - ✅ Enable Apple Pay is checked
   - ✅ Apple Pay Merchant ID is filled
   - ✅ Merchant ID format: `merchant.com.yourcompany.yoco`

### Common Issues

**Issue**: Apple Pay shows but payment fails
**Solution**: 
- Verify Apple Merchant ID with Apple Developer account
- Ensure domain is verified with Apple
- Contact Yoco to confirm Apple Pay is enabled for your account

**Issue**: Apple Pay doesn't show on iPhone
**Solution**:
- Ensure site is HTTPS
- Check if Wallet app has cards configured
- Verify Touch ID/Face ID is enabled

## 📱 Device Support Matrix

| Device/Browser | Apple Pay Support |
|----------------|-------------------|
| iPhone Safari | ✅ Yes |
| iPad Safari | ✅ Yes |
| Mac Safari | ✅ Yes |
| Mac Chrome | ✅ Yes (if enabled) |
| Windows Chrome | ❌ No |
| Android Chrome | ❌ No |
| Firefox (any) | ❌ No |

## 🚀 Production Checklist

Before going live with Apple Pay:

- [ ] Apple Developer account setup
- [ ] Merchant ID created and verified
- [ ] Domain verification completed
- [ ] Yoco merchant account approved for Apple Pay
- [ ] HTTPS certificate installed
- [ ] Tested on Safari (macOS/iOS)
- [ ] Tested payment flow end-to-end
- [ ] Verified ERPNext integration works

## 📞 Support

If you need help:

1. **Apple Pay Setup**: Contact Apple Developer Support
2. **Yoco Integration**: Contact Yoco Merchant Support
3. **ERPNext Issues**: Check the main payment gateway documentation

The Apple Pay integration is now ready and will automatically appear for supported devices/browsers when properly configured!
