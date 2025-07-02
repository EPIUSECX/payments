$(document).ready(function() {
    $('#yoco-payment-button').on('click', function(e) {
        e.preventDefault();

        var yoco = new YocoSDK({
            publicKey: '{{ api_key }}',
        });

        yoco.showPopup({
            amountInCents: {{ amount * 100 }},
            currency: '{{ currency }}',
            name: '{{ title }}',
            description: '{{ description }}',
            paymentMethods: ['card', 'applePay', 'googlePay', 'instantEFT'],
            callback: function (result) {
                if (result.error) {
                    frappe.show_alert({
                        message: result.error.message,
                        indicator: 'red'
                    });
                } else {
                    frappe.call({
                        method: "payments.templates.pages.yoco_checkout.make_payment",
                        headers: {"X-Requested-With": "XMLHttpRequest"},
                        args: {
                            "yoco_token": result.id,
                            "data": JSON.stringify({{ frappe.form_dict|json }}),
                            "reference_doctype": "{{ reference_doctype }}",
                            "reference_docname": "{{ reference_docname }}",
                            "payment_gateway_account": "{{ payment_gateway_account }}"
                        },
                        callback: function(r) {
                            if (r.message.status == "Completed") {
                                window.location.href = r.message.redirect_to;
                            } else {
                                window.location.href = r.message.redirect_to;
                            }
                        }
                    });
                }
            }
        });
    });
});