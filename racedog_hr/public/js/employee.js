// Employee form — a one-click "Create Portal Login" for managers/recruiters, so a
// consultant gets self-service access without hand-creating + linking a User.

frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (frm.is_new()) return;

		const canOnboard = frappe.user.has_role([
			"Recruiting Manager",
			"System Manager",
			"HR Manager",
			"Recruiter",
			"Bench Sales",
		]);
		if (!canOnboard) return;

		// Submissions + interview history + client feedback for this candidate.
		frm.add_custom_button(__("Pipeline & Interviews"), () => {
			frappe.set_route("candidate-pipeline", { consultant: frm.doc.name });
		});

		// Rates live on the manager-only Consultant Billing DocType (not on this
		// form). Give managers a one-click way to open/create it.
		if (frappe.user.has_role(["Recruiting Manager", "Account Manager", "System Manager"])) {
			frm.add_custom_button(__("Billing"), () => {
				frappe.db.exists("Consultant Billing", frm.doc.name).then((exists) => {
					if (exists) {
						frappe.set_route("Form", "Consultant Billing", frm.doc.name);
					} else {
						frappe.new_doc("Consultant Billing", { consultant: frm.doc.name });
					}
				});
			});
		}

		// Already linked -> show a gentle indicator; otherwise offer the one-click
		// login (manager-gated, so only show it to managers).
		if (frm.doc.user_id) {
			frm.dashboard.add_indicator(__("Portal login: {0}", [frm.doc.user_id]), "green");
			return;
		}
		if (!frappe.user.has_role(["Recruiting Manager", "HR Manager", "System Manager"])) return;

		frm.add_custom_button(
			__("Create Portal Login"),
			() => {
				frappe.confirm(
					__(
						"Give {0} a login to their self-service portal? A user is created with the Employee role and linked to this record.",
						[frm.doc.employee_name || frm.doc.name]
					),
					() => {
						frappe.call({
							method: "racedog_hr.api.create_consultant_login",
							args: { employee: frm.doc.name },
							freeze: true,
							freeze_message: __("Creating login…"),
							callback: (r) => {
								const d = r.message && r.message.data;
								if (!d) return;
								let msg = __("Login e-mail: <b>{0}</b>", [d.user]);
								if (d.temp_password) {
									msg +=
										"<br><br>" +
										__("Temporary password: <b>{0}</b>", [d.temp_password]) +
										"<br>" +
										__("Share these with the consultant — they can change the password after logging in.");
								} else {
									msg += "<br>" + __("This user already existed and is now linked.");
								}
								frappe.msgprint({
									title: __("Portal login ready"),
									message: msg,
									indicator: "green",
								});
								frm.reload_doc();
							},
						});
					}
				);
			},
			__("Actions")
		);
	},
});
