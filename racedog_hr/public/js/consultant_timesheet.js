// Consultant Timesheet form — HR approve/reject actions. HR reviews from the standard
// List (filter by status/client/period), opens a row, views the PDF, and acts here.

frappe.ui.form.on("Consultant Timesheet", {
	refresh(frm) {
		if (frm.is_new()) return;

		const isHR = frappe.user.has_role(["HR Manager", "Recruiting Manager", "System Manager"]);
		if (!isHR) return;

		if (frm.doc.status === "Approved") {
			frm.dashboard.add_indicator(__("Approved"), "green");
			return;
		}

		frm.add_custom_button(__("Approve"), () => {
			frappe.confirm(__("Approve this timesheet? The consultant is notified."), () => {
				frappe.call({
					method: "racedog_hr.api.approve_timesheet",
					args: { timesheet: frm.doc.name },
					freeze: true,
					callback: () => {
						frappe.show_alert({ message: __("Approved"), indicator: "green" }, 4);
						frm.reload_doc();
					},
				});
			});
		}).addClass("btn-primary");

		frm.add_custom_button(__("Reject"), () => {
			frappe.prompt(
				[
					{
						fieldname: "note",
						fieldtype: "Small Text",
						label: __("Reason (shown to the consultant)"),
						reqd: 1,
					},
				],
				(v) => {
					frappe.call({
						method: "racedog_hr.api.reject_timesheet",
						args: { timesheet: frm.doc.name, note: v.note },
						freeze: true,
						callback: () => {
							frappe.show_alert({ message: __("Rejected — consultant notified"), indicator: "orange" }, 5);
							frm.reload_doc();
						},
					});
				},
				__("Reject timesheet"),
				__("Send")
			);
		});
	},
});
