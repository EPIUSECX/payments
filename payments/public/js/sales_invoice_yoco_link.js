frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        if (frm.doc.docstatus === 1 && (frm.doc.outstanding_amount || 0) > 0 && (frm.doc.currency === 'ZAR' || !frm.doc.currency)) {
            frm.add_custom_button(__('Send Yoco Payment Link'), async () => {
                try {
                    frm.dashboard.clear_comment();
                    frm.dashboard.show_progress(__('Generating link...'), 50);

                    const r = await frappe.call({
                        method: 'payments.api.payment_links.create_payment_link_for_sales_invoice',
                        args: { sales_invoice: frm.doc.name },
                    });

                    frm.dashboard.hide();

                    if (r.message) {
                        const { payment_url, recipient } = r.message;
                        const html = `
                            <div>
                                <p>${__('Yoco payment link generated.')}</p>
                                <p><a href="${payment_url}" target="_blank" rel="noopener">${__('Open Payment Link')}</a></p>
                                ${recipient ? `<p>${__('Email sent to')}: <b>${frappe.utils.escape_html(recipient)}</b></p>` : ''}
                            </div>`;
                        frm.dashboard.set_headline_alert(html, 'blue');
                        frappe.msgprint({
                            title: __('Payment Link'),
                            message: html,
                            indicator: 'blue'
                        });
                    }
                } catch (e) {
                    frm.dashboard.hide();
                    frappe.msgprint({
                        title: __('Error'),
                        message: e.message || __('Failed to create payment link'),
                        indicator: 'red'
                    });
                }
            }, __('Actions'));
        }
    }
});


