$(document).ready(function() {
    $('#yoco-payment-button').on('click', function(e) {
        e.preventDefault();

        var yoco = new YocoSDK({
            publicKey: '{{ api_key }}'
        });

        yoco.showPopup({
            amountInCents: parseInt({{ amount }} * 100),
            currency: '{{ currency }}',
            name: '{{ title }}',
            description: '{{ description }}',
            paymentMethods: ['card', 'applePay', 'googlePay', 'instantEFT'],
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
                } else {
                    // Show loading indicator
                    frappe.show_alert({
                        message: 'Processing payment...',
                        indicator: 'blue'
                    });

                    var paymentData = {
                        "amount": {{ amount }},
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
        });
    });
});
