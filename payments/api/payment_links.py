import json

import frappe
from frappe import _


def _find_yoco_payment_gateway_account(company: str) -> dict | None:
    # Prefer default PGA for company where gateway starts with "Yoco-"
    pga = frappe.db.get_value(
        "Payment Gateway Account",
        {
            "company": company,
            "is_default": 1,
            "payment_gateway": ["like", "Yoco-%"],
        },
        ["name", "payment_gateway", "payment_account", "message"],
        as_dict=True,
    )
    if pga:
        return pga

    # Fallback to any Yoco PGA for company
    pga = frappe.db.get_value(
        "Payment Gateway Account",
        {
            "company": company,
            "payment_gateway": ["like", "Yoco-%"],
        },
        ["name", "payment_gateway", "payment_account", "message"],
        as_dict=True,
    )
    return pga


@frappe.whitelist()
def create_payment_link_for_sales_invoice(sales_invoice: str) -> dict:
    """
    Create a Payment Request for a submitted Sales Invoice and return a Yoco checkout link.
    Sends an email to the customer and logs a Communication.
    """
    si = frappe.get_doc("Sales Invoice", sales_invoice)

    if si.docstatus != 1:
        frappe.throw(_("Sales Invoice must be submitted."))

    if si.outstanding_amount <= 0:
        frappe.throw(_("Sales Invoice has no outstanding amount."))

    # ZAR only for Yoco
    if si.currency and si.currency != "ZAR":
        frappe.throw(_("Yoco payment links only support ZAR invoices."))

    pga = _find_yoco_payment_gateway_account(si.company)
    if not pga:
        frappe.throw(_("No Yoco Payment Gateway Account configured for this company."))

    # Resolve recipient email
    recipient = getattr(si, "contact_email", None) or frappe.db.get_value("Customer", si.customer, "email_id")

    from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request

    pr = make_payment_request(
        dt="Sales Invoice",
        dn=si.name,
        payment_gateway_account=pga.get("name"),
        submit_doc=1,
        mute_email=1,
        return_doc=1,
    )

    payment_url = pr.payment_url
    if not payment_url:
        # Fallback: try to set the URL explicitly using controller
        try:
            pr.set_payment_request_url()
            pr.reload()
            payment_url = pr.payment_url
        except Exception:
            pass

    if not payment_url:
        frappe.throw(_("Failed to generate Yoco payment URL."))

    # Email the link and log communication
    if recipient:
        subject = _("Payment link for Sales Invoice {0}").format(si.name)
        message = (
            f"<p>Dear Customer,</p>"
            f"<p>Please use the link below to pay Sales Invoice <b>{frappe.utils.escape_html(si.name)}</b>:</p>"
            f"<p><a href=\"{frappe.utils.escape_html(payment_url)}\" target=\"_blank\" rel=\"noopener\">Pay Now via Yoco</a></p>"
            f"<p>Amount Due: {frappe.utils.fmt_money(si.outstanding_amount, currency=si.currency)}</p>"
        )

        frappe.sendmail(recipients=[recipient], subject=subject, message=message)

        comm = frappe.get_doc(
            {
                "doctype": "Communication",
                "subject": subject,
                "content": message,
                "sent_or_received": "Sent",
                "reference_doctype": si.doctype,
                "reference_name": si.name,
            }
        )
        comm.insert(ignore_permissions=True)

    return {
        "payment_request": pr.name,
        "payment_url": payment_url,
        "recipient": recipient,
        "message": _("Yoco payment link generated successfully."),
    }


