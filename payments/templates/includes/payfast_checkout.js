$(document).ready(function() {
    $('#payfast-payment-button').on('click', function(e) {
        e.preventDefault();
        window.location.href = '{{ payment_url }}';
    });
});