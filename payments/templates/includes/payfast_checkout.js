$(document).ready(function() {
    $('#payfast-payment-button').on('click', function(e) {
        e.preventDefault();
        
        console.log('[PAYFAST DEBUG] Payment button clicked, calling get_payment_url');
        
        // Disable button to prevent double-clicks
        var $button = $(this);
        $button.prop('disabled', true).text('Processing...');

        frappe.call({
            method: "payments.templates.pages.payfast_checkout.get_payment_url",
            args: {
                token: "{{ token }}"
            },
            callback: function(r) {
                console.log('[PAYFAST DEBUG] Received response:', r);
                
                if (r.message && r.message.payfast_url && r.message.form_data) {
                    console.log('[PAYFAST DEBUG] Creating PayFast form for redirect');
                    
                    // Create form dynamically to POST to PayFast
                    var form = $('<form>', {
                        'method': 'POST',
                        'action': r.message.payfast_url
                    });
                    
                    // Add all form fields
                    $.each(r.message.form_data, function(key, value) {
                        form.append($('<input>', {
                            'type': 'hidden',
                            'name': key,
                            'value': value
                        }));
                    });
                    
                    console.log('[PAYFAST DEBUG] Submitting form to:', r.message.payfast_url);
                    console.log('[PAYFAST DEBUG] Form data:', r.message.form_data);
                    
                    // Append form to body and submit
                    $('body').append(form);
                    form.submit();
                } else if (r.message && r.message.redirect_to) {
                    // Handle error redirect
                    console.log('[PAYFAST DEBUG] Redirecting to error page:', r.message.redirect_to);
                    window.location.href = r.message.redirect_to;
                } else {
                    console.error('[PAYFAST DEBUG] Invalid response format:', r);
                    $button.prop('disabled', false).text('Pay with Payfast');
                    frappe.show_alert({
                        message: 'Could not get payment data. Please try again.',
                        indicator: 'red'
                    });
                }
            },
            error: function(r) {
                console.error('[PAYFAST DEBUG] Error occurred:', r);
                $button.prop('disabled', false).text('Pay with Payfast');
                frappe.show_alert({
                    message: 'An error occurred. Please try again.',
                    indicator: 'red'
                });
            }
        });
    });
});
