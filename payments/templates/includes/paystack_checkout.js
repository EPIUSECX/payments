frappe.call({
    method: "payments.templates.pages.paystack_checkout.get_paystack_payment_url",
    headers: {"X-Requested-With": "XMLHttpRequest"},
    args: {
        token: "{{ token }}"
    },
    callback: function(r) {
        if (r.message) {
            window.location.href = r.message;
        }
    }
});