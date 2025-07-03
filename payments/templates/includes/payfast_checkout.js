$(document).ready(function() {
    $('#payfast-payment-button').on('click', function(e) {
        e.preventDefault();

        frappe.call({
            method: "payments.templates.pages.payfast_checkout.get_payment_url",
            args: {
                token: "{{ token }}"
            },
            callback: function(r) {
                if (r.message) {
                    window.location.href = r.message;
                } else {
                    frappe.show_alert({
                        message: 'Could not get payment URL. Please try again.',
                        indicator: 'red'
                    });
                }
            },
            error: function(r) {
                frappe.show_alert({
                    message: 'An error occurred. Please try again.',
                    indicator: 'red'
                });
            }
        });
    });
});
