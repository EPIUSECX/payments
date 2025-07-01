var yoco = new YocoSDK({
    publicKey: '{{ api_key }}',
});

frappe.call({
    method: "payments.templates.pages.yoco_checkout.get_yoco_payment_id",
    headers: {"X-Requested-With": "XMLHttpRequest"},
    args: {
        token: "{{ token }}"
    },
    callback: function(r) {
        if (r.message) {
            yoco.showPopup({
                amountInCents: {{ amount * 100 }},
                currency: '{{ currency }}',
                name: '{{ title }}',
                description: '{{ description }}',
                callback: function (result) {
                    if (result.error) {
                        frappe.show_alert({
                            message: result.error.message,
                            indicator: 'red'
                        });
                    } else {
                        window.location.href = result.successUrl;
                    }
                }
            })
        }
    }
});