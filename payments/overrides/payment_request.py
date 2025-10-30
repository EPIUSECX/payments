import time

import frappe
from frappe import _
from erpnext.accounts.doctype.payment_request.payment_request import PaymentRequest as _ERPNextPaymentRequest


class PaymentRequest(_ERPNextPaymentRequest):
    def on_payment_authorized(self, payment_status: str | None = None):
        """
        ERPNext-compatible callback invoked by payment gateways on success.

        Behavior per requirements:
        - Only handle full, successful payments for Sales Orders (ZAR)
        - Auto-submit Payment Entry immediately
        - Retry automatically on transient failures, then alert admins
        """
        try:
            # Fast path: only proceed on explicit success
            if payment_status and payment_status != "Completed":
                frappe.log_error(
                    f"Payment authorization callback ignored due to status: {payment_status}",
                    "Payment Request Authorization Skipped",
                )
                return

            # Constraints per user requirements
            if self.reference_doctype != "Sales Order":
                frappe.log_error(
                    f"on_payment_authorized called for unsupported doctype: {self.reference_doctype}",
                    "Payment Request Authorization Unsupported",
                )
                return

            # Only ZAR for Yoco/PayFast flows; allow if unset
            if self.currency and self.currency != "ZAR":
                frappe.throw(_(f"Unsupported currency for this gateway flow: {self.currency}"))

            # Idempotency: if already Paid/outstanding 0, exit quietly
            if getattr(self, "status", "") == "Paid" or not getattr(self, "outstanding_amount", 0):
                return

            # Retry policy: 3 attempts with small backoff
            last_error = None
            for attempt in range(1, 4):
                try:
                    # set_as_paid creates and submits Payment Entry immediately
                    pe = self.set_as_paid()
                    # Some flows return PE document; others None after submission
                    frappe.db.commit()
                    frappe.log_error(
                        f"Payment Request {self.name} marked as Paid on attempt {attempt}",
                        "Payment Request Authorization Success",
                    )
                    return pe
                except Exception as e:  # noqa: BLE001
                    last_error = e
                    frappe.log_error(
                        f"Attempt {attempt} to set_as_paid failed for PR {self.name}: {str(e)}\n{frappe.get_traceback()}",
                        "Payment Request Authorization Retry",
                    )
                    # Simple backoff: 0.5s, 1s
                    if attempt < 3:
                        time.sleep(0.5 * attempt)

            # After retries failed, alert admins and re-raise
            self._alert_admins_on_failure(last_error)
            raise last_error

        except Exception:  # noqa: BLE001
            # Ensure exceptions are visible to callers/webhooks
            frappe.log_error(frappe.get_traceback(), "Payment Request Authorization Error")
            raise

    def _alert_admins_on_failure(self, error: Exception | None):
        try:
            # Resolve System Managers
            sys_manager_users = [r.parent for r in frappe.get_all(
                "Has Role", filters={"role": "System Manager"}, fields=["parent"]
            )]
            sys_manager_users = [u for u in sys_manager_users if frappe.db.get_value("User", u, "enabled")]

            if not sys_manager_users:
                return

            subject = _("Payment Processing Failed for Payment Request {0}").format(self.name)
            message = (
                f"<p>Automatic payment completion failed for Payment Request <b>{self.name}</b>.</p>"
                f"<p><b>Reference:</b> {self.reference_doctype} {self.reference_name}</p>"
                f"<p><b>Error:</b> {frappe.as_unicode(error) if error else 'Unknown error'}</p>"
                f"<p>Please review the Integration Request and GL entries.</p>"
            )

            frappe.sendmail(recipients=sys_manager_users, subject=subject, message=message)
        except Exception:  # noqa: BLE001
            # Do not block main flow on alert failure
            frappe.log_error(frappe.get_traceback(), "Payment Request Authorization Admin Alert Error")


