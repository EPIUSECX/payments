// Copyright (c) 2024, [Your Name] and contributors
// License: MIT. See LICENSE

frappe.ui.form.on('Yoco Settings', {
	// client-side scripts for Yoco Settings
    // TODO: Implement client-side integration with Yoco SDK for tokenization

    refresh: function(frm) {
        frm.add_custom_button(__('Test Connection'), function() {
            frm.call({
                method: 'test_connection',
                doc: frm.doc,
                callback: function(r) {
                    if (r.message.status === 'success') {
                        frappe.msgprint(__('Connection successful!'));
                    } else {
                        frappe.msgprint(__('Connection failed: ') + r.message.message, __('Error'));
                    }
                }
            });
        });
    }
});
