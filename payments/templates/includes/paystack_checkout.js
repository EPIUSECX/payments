$(document).ready(function() {
    $('#paystack-payment-button').on('click', function(e) {
        e.preventDefault();

        let handler = PaystackPop.setup({
            key: '{{ api_key }}',
            email: '{{ payer_email }}',
            amount: {{ amount * 100 }},
            currency: '{{ currency }}',
            ref: '{{ reference_docname }}',
            callback: function(response) {
                frappe.call({
                    method: "payments.templates.pages.paystack_checkout.make_payment",
                    headers: {"X-Requested-With": "XMLHttpRequest"},
                    args: {
                        "paystack_txn_ref": response.reference,
                        "data": JSON.stringify({{ frappe.form_dict|json }}),
                        "reference_doctype": "{{ reference_doctype }}",
                        "reference_docname": "{{ reference_docname }}",
                    },
                    callback: function(r) {
                        if (r.message.status == "Completed") {
                            window.location.href = r.message.redirect_to;
                        } else {
                            window.location.href = r.message.redirect_to;
                        }
                    }
                });
            },
            onClose: function() {
                // user closed popup
            }
        });
        handler.openIframe();
    });
});