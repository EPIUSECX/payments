$(document).ready(function() {
    $('#yoco-payment-button').on('click', function(e) {
        e.preventDefault();

        var yoco = new YocoSDK({
            publicKey: '{{ api_key }}'
        });

        // Build payment methods array
        var paymentMethods = ['card', 'googlePay', 'instantEFT'];
        
        // Add Apple Pay if enabled and merchant ID is configured
        {% if enable_apple_pay and apple_pay_merchant_id %}
        paymentMethods.push('applePay');
        {% endif %}

        var popupConfig = {
            amountInCents: parseInt('{{ amount }}' * 100),
            currency: '{{ currency }}',
            name: '{{ title }}',
            description: '{{ description }}',
            paymentMethods: paymentMethods,
            metadata: {
                integration_request: '{{ token }}',
                reference_doctype: '{{ reference_doctype }}',
                reference_docname: '{{ reference_docname }}'
            },
            callback: function (result) {
                if (result.error) {
                    frappe.show_alert({
                        message: result.error.message,
                        indicator: 'red'
                    });
                    // Redirect to payment failed page
                    window.location.href = '/payment-failed';
                } else {
                    // Payment successful - process immediately since webhooks may not be configured
                    frappe.show_alert({
                        message: 'Payment successful! Processing...',
                        indicator: 'blue'
                    });

                    var paymentData = {
                        "amount": '{{ amount }}',
                        "currency": "{{ currency }}",
                        "title": "{{ title }}",
                        "description": "{{ description }}",
                        "reference_doctype": "{{ reference_doctype }}",
                        "reference_docname": "{{ reference_docname }}",
                        "token": "{{ token }}"
                    };

                    frappe.call({
                        method: "payments.templates.pages.yoco_checkout.make_payment",
                        headers: {"X-Requested-With": "XMLHttpRequest"},
                        args: {
                            "yoco_token": result.id,
                            "data": JSON.stringify(paymentData),
                            "reference_doctype": "{{ reference_doctype }}",
                            "reference_docname": "{{ reference_docname }}",
                            "payment_gateway_account": "{{ payment_gateway_account }}"
                        },
                        callback: function(r) {
                            if (r.message && r.message.redirect_to) {
                                window.location.href = r.message.redirect_to;
                            } else {
                                frappe.show_alert({
                                    message: 'Payment processing failed. Please try again.',
                                    indicator: 'red'
                                });
                            }
                        },
                        error: function(r) {
                            frappe.show_alert({
                                message: 'Payment processing failed. Please try again.',
                                indicator: 'red'
                            });
                        }
                    });
                }
            }
        };

        // Add Apple Pay specific configuration if enabled
        {% if enable_apple_pay and apple_pay_merchant_id %}
        popupConfig.applePay = {
            merchantIdentifier: '{{ apple_pay_merchant_id }}',
            merchantCapabilities: ['supports3DS', 'supportsCredit', 'supportsDebit'],
            supportedNetworks: ['visa', 'masterCard', 'amex', 'discover']
        };
        {% endif %}

        // Show the Yoco payment popup
        yoco.showPopup(popupConfig);
    });
});
