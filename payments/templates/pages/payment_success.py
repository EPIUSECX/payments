# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe

no_cache = True


def get_context(context):
	# Handle missing or invalid document parameters gracefully
	doctype = frappe.local.form_dict.get("doctype")
	docname = frappe.local.form_dict.get("docname")

	context.payment_message = ""
	context.doc = None
	context.error_message = ""

	if doctype and docname:
		try:
			doc = frappe.get_doc(doctype, docname)
			context.doc = doc
			if hasattr(doc, "get_payment_success_message"):
				context.payment_message = doc.get_payment_success_message()
			else:
				context.payment_message = _("Payment completed successfully!")
		except Exception as e:
			context.error_message = _("Document not found or access denied.")
			context.payment_message = _("Payment completed successfully!")
			frappe.log_error(f"Payment success page error: {str(e)}", "Payment Success Page")
	else:
		# No document specified - generic success message
		context.payment_message = _("Payment completed successfully!")
