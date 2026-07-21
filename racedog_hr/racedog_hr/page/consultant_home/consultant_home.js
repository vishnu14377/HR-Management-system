// Consultant Home — a W2 consultant's self-service dashboard. Reads/writes ONLY
// through whitelisted racedog_hr.api methods scoped to the caller's own record,
// so rates/margin never reach the client and no other consultant is visible.

frappe.pages["consultant-home"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("My Home"),
		single_column: true,
	});
	page.set_secondary_action(__("Refresh"), () => home.reload(), "refresh");
	const home = new ConsultantHome(page);
};

const DOC_TYPES = [
	"Resume",
	"Visa",
	"Work Authorization (EAD/I-797)",
	"Driver License",
	"Passport",
	"Offer Letter",
	"Other",
];

// Submission stages the consultant sees, with a friendly tone + color.
const SUB_STAGE = {
	"Submitted": { label: "Submitted", tone: "info" },
	"Under Review": { label: "Under Review", tone: "info" },
	"Interview Scheduled": { label: "Interview Scheduled", tone: "warn" },
	"Interview Done": { label: "Interview Done", tone: "warn" },
	"Offer": { label: "Offer", tone: "good" },
	"Placed": { label: "Placed", tone: "good" },
	"Rejected": { label: "Not Selected", tone: "muted" },
	"Withdrawn": { label: "Withdrawn", tone: "muted" },
};

class ConsultantHome {
	constructor(page) {
		this.page = page;
		this.$root = $('<div class="rdg-home">').appendTo(page.main);
		this.reload();
	}

	reload() {
		this.$root.html('<div class="rdg-home-loading">' + __("Loading your dashboard…") + "</div>");
		frappe.call({
			method: "racedog_hr.api.get_my_profile",
			callback: (r) => {
				this.profile = (r.message && r.message.data) || null;
				this.render();
				this.load_submissions();
			},
			error: (e) => this.render_unlinked(e),
		});
	}

	render_unlinked() {
		this.$root.html(`
			<div class="rdg-home-empty">
				<h2>${__("Welcome")}</h2>
				<p>${__(
					"Your login isn't linked to a consultant profile yet. Please ask your recruiting manager to connect your account, then refresh."
				)}</p>
			</div>
		`);
	}

	render() {
		const p = this.profile;
		if (!p) return this.render_unlinked();
		const esc = frappe.utils.escape_html;
		const initials = (p.employee_name || "?")
			.split(" ")
			.map((s) => s[0])
			.slice(0, 2)
			.join("")
			.toUpperCase();
		const avatar = p.image ? `style="background-image:url('${encodeURI(p.image)}')"` : "";

		this.$root.html(`
			<header class="rdg-hero">
				<div class="rdg-hero-avatar" ${avatar}>${avatar ? "" : esc(initials)}</div>
				<div class="rdg-hero-id">
					<h1>${esc(p.employee_name || "")}</h1>
					<div class="rdg-hero-role">${esc(p.designation || __("Consultant"))}</div>
				</div>
				<div class="rdg-hero-status">
					<span class="rdg-status-pill" data-s="${esc(p.deployment_status || "")}">${esc(
						p.deployment_status || "—"
					)}</span>
					${
						p.hotlist
							? `<span class="rdg-hot" data-hot="${esc(p.hotlist)}">${esc(p.hotlist)}</span>`
							: ""
					}
				</div>
			</header>

			<section class="rdg-grid">
				${this.status_card(p)}
				${this.workauth_card(p)}
				${this.owner_card(p)}
			</section>

			<section class="rdg-panel">
				<div class="rdg-panel-head"><h3>${__("My Submissions")}</h3><span class="rdg-sub-count"></span></div>
				<div class="rdg-subs">${__("Loading…")}</div>
			</section>

			<section class="rdg-panel">
				<div class="rdg-panel-head"><h3>${__("My Timesheets")}</h3><span class="rdg-ts-owed"></span></div>
				${this.ts_upload_form()}
				<div class="rdg-ts">${__("Loading…")}</div>
			</section>

			<section class="rdg-two">
				<div class="rdg-panel">
					<div class="rdg-panel-head"><h3>${__("My Documents")}</h3></div>
					<div class="rdg-docs"></div>
					${this.upload_form()}
				</div>
				<div class="rdg-panel">
					<div class="rdg-panel-head"><h3>${__("Update My Info")}</h3></div>
					${this.edit_form(p)}
				</div>
			</section>
		`);

		this.render_docs(p.documents || []);
		this.bind_upload();
		this.bind_edit();
		this.bind_ts_upload();
		this.load_timesheets();
	}

	ts_upload_form() {
		return `
			<div class="rdg-upload">
				<select class="rdg-ts-month" title="${__("Billing month")}"></select>
				<input class="rdg-ts-hours" type="number" min="0" step="0.5" placeholder="${__("Hours (optional)")}">
				<input class="rdg-ts-file" type="file" accept=".pdf">
				<button class="rdg-btn rdg-ts-go">${__("Upload timesheet")}</button>
			</div>
			<div class="rdg-u-hint rdg-muted">${__("Upload your client-signed monthly timesheet (PDF, up to 10 MB). HR reviews it. Only you and HR can see it.")}</div>`;
	}

	load_timesheets() {
		frappe.call({
			method: "racedog_hr.api.get_my_timesheets",
			callback: (r) => this.render_timesheets((r.message && r.message) || {}),
			error: () => this.$root.find(".rdg-ts").html(`<div class="rdg-muted">${__("Could not load.")}</div>`),
		});
	}

	render_timesheets(payload) {
		const esc = frappe.utils.escape_html;
		const rows = payload.data || [];
		const owed = payload.owed || [];

		// Month picker = owed months (most useful) + a couple recent ones, deduped.
		const months = [];
		owed.forEach((o) => months.push(o.period_month));
		const submitted = rows.map((r) => r.period_month);
		submitted.forEach((m) => { if (!months.includes(m)) months.push(m); });
		const $sel = this.$root.find(".rdg-ts-month").empty();
		months.forEach((m) => $sel.append(`<option value="${esc(m)}">${esc(m)}</option>`));
		if (payload.default_period) $sel.val(payload.default_period);

		// "Owed" banner — only the required ones (bench months aren't chased).
		const required = owed.filter((o) => o.required).map((o) => o.period_month);
		const $owed = this.$root.find(".rdg-ts-owed");
		if (required.length) {
			$owed.html(`<span class="rdg-count" data-tone="warn">${__("Owed: {0}", [required.join(", ")])}</span>`);
		} else if (owed.length) {
			$owed.text(__("Bench months — no timesheet required"));
		} else {
			$owed.text(__("All caught up"));
		}

		const $t = this.$root.find(".rdg-ts");
		if (!rows.length) {
			$t.html(`<div class="rdg-muted">${__("No timesheets uploaded yet. Pick the month above and upload your signed PDF.")}</div>`);
			return;
		}
		const TONE = { Submitted: "info", "Under Review": "warn", Approved: "good", Rejected: "muted" };
		$t.html(
			rows
				.map((s) => {
					const tone = TONE[s.status] || "info";
					const label = s.status === "Rejected" ? __("Needs changes") : s.status;
					const hours = s.total_hours ? ` · ${s.total_hours} ${__("hrs")}` : "";
					return `
						<div class="rdg-sub">
							<div class="rdg-sub-main">
								<div class="rdg-sub-title">${esc(s.period_month)}${esc(hours)}</div>
								<div class="rdg-sub-sub">
									${s.signed_pdf ? `<a href="${encodeURI(s.signed_pdf)}" target="_blank" rel="noopener">${__("View PDF")}</a>` : ""}
									${s.client ? " · " + esc(s.client) : ""}
								</div>
								${s.status === "Rejected" && s.review_note ? `<div class="rdg-sub-fb">${__("HR")}: ${esc(s.review_note)}</div>` : ""}
							</div>
							<span class="rdg-stage" data-tone="${tone}">${esc(label)}</span>
						</div>`;
				})
				.join("")
		);
	}

	bind_ts_upload() {
		this.$root.find(".rdg-ts-go").on("click", () => {
			const month = this.$root.find(".rdg-ts-month").val();
			const hours = this.$root.find(".rdg-ts-hours").val();
			const fileInput = this.$root.find(".rdg-ts-file")[0];
			const file = fileInput && fileInput.files && fileInput.files[0];
			if (!month) { frappe.msgprint(__("Pick a month.")); return; }
			if (!file) { frappe.msgprint(__("Choose your timesheet PDF.")); return; }
			if (!/\.pdf$/i.test(file.name)) { frappe.msgprint(__("The timesheet must be a PDF.")); return; }
			if (file.size > 10 * 1024 * 1024) { frappe.msgprint(__("That file is larger than 10 MB.")); return; }
			const reader = new FileReader();
			reader.onload = () => {
				frappe.call({
					method: "racedog_hr.api.upload_my_timesheet",
					args: { period_month: month, file_name: file.name, content: reader.result, total_hours: hours || null },
					freeze: true,
					freeze_message: __("Uploading…"),
					callback: () => {
						frappe.show_alert({ message: __("Timesheet submitted for {0}", [month]), indicator: "green" }, 4);
						this.reload();
					},
					error: () => frappe.show_alert({ message: __("Upload failed"), indicator: "red" }, 6),
				});
			};
			reader.readAsDataURL(file);
		});
	}

	status_card(p) {
		const esc = frappe.utils.escape_html;
		const avail = p.availability_date
			? frappe.datetime.str_to_user(p.availability_date)
			: __("Available now");
		const client =
			p.deployment_status === "Working" && p.current_client
				? `<div class="rdg-kv"><span>${__("Current Client")}</span><b>${esc(
						p.current_client
				  )}</b></div>`
				: "";
		const skills = (p.skills || []).map((s) => `<span class="rdg-tag">${esc(s)}</span>`).join("");
		return `
			<div class="rdg-card">
				<div class="rdg-card-title">${__("My Status")}</div>
				<div class="rdg-kv"><span>${__("Status")}</span><b>${esc(p.deployment_status || "—")}</b></div>
				${client}
				<div class="rdg-kv"><span>${__("Available From")}</span><b>${esc(avail)}</b></div>
				${skills ? `<div class="rdg-tags">${skills}</div>` : ""}
			</div>`;
	}

	workauth_card(p) {
		const esc = frappe.utils.escape_html;
		let countdown = "";
		if (p.visa_expiry) {
			const days = frappe.datetime.get_day_diff(p.visa_expiry, frappe.datetime.get_today());
			const tone = days < 0 ? "bad" : days <= 30 ? "warn" : "good";
			const txt =
				days < 0
					? __("Expired")
					: days === 0
					? __("Expires today")
					: __("{0} days left", [days]);
			countdown = `<span class="rdg-count" data-tone="${tone}">${esc(txt)}</span>`;
		}
		return `
			<div class="rdg-card">
				<div class="rdg-card-title">${__("Work Authorization")}</div>
				<div class="rdg-kv"><span>${__("Type")}</span><b>${esc(p.visa_status || "—")}</b></div>
				<div class="rdg-kv"><span>${__("Expires")}</span><b>${
					p.visa_expiry ? esc(frappe.datetime.str_to_user(p.visa_expiry)) : "—"
				} ${countdown}</b></div>
			</div>`;
	}

	owner_card(p) {
		const esc = frappe.utils.escape_html;
		const c = p.marketing_owner_contact;
		if (!c) {
			return `
				<div class="rdg-card">
					<div class="rdg-card-title">${__("My Recruiter")}</div>
					<div class="rdg-muted">${__("No marketing owner assigned yet.")}</div>
				</div>`;
		}
		return `
			<div class="rdg-card">
				<div class="rdg-card-title">${__("My Recruiter")}</div>
				<div class="rdg-kv"><span>${__("Name")}</span><b>${esc(c.name || "—")}</b></div>
				${
					c.email
						? `<div class="rdg-kv"><span>${__("Email")}</span><a href="mailto:${esc(
								c.email
						  )}">${esc(c.email)}</a></div>`
						: ""
				}
				${
					c.phone
						? `<div class="rdg-kv"><span>${__("Phone")}</span><a href="tel:${esc(
								c.phone
						  )}">${esc(c.phone)}</a></div>`
						: ""
				}
			</div>`;
	}

	load_submissions() {
		frappe.call({
			method: "racedog_hr.api.get_my_submissions",
			callback: (r) => this.render_submissions((r.message && r.message.data) || []),
			error: () => this.$root.find(".rdg-subs").html(`<div class="rdg-muted">${__("Could not load.")}</div>`),
		});
	}

	render_submissions(rows) {
		const esc = frappe.utils.escape_html;
		this.$root.find(".rdg-sub-count").text(`${rows.length} ${__("total")}`);
		const $t = this.$root.find(".rdg-subs");
		if (!rows.length) {
			$t.html(
				`<div class="rdg-muted">${__(
					"No active submissions yet. Your recruiter markets you against open requirements."
				)}</div>`
			);
			return;
		}
		$t.html(
			rows
				.map((s) => {
					const stage = SUB_STAGE[s.status] || { label: s.status, tone: "info" };
					const when = s.interview_datetime
						? __("Interview: {0}", [frappe.datetime.str_to_user(s.interview_datetime)])
						: s.submitted_on
						? __("Submitted {0}", [frappe.datetime.str_to_user(s.submitted_on)])
						: "";
					const client = s.client ? esc(s.client) : __("(client shared at interview)");
					// Candidate-safe interview rounds — date/type/outcome only, NO feedback.
					const OUT = { Scheduled: "info", Cleared: "good", Rejected: "muted", "On Hold": "warn", "No Show": "muted" };
					const rounds = (s.interviews || [])
						.map((iv) => {
							const d = iv.interview_date ? frappe.datetime.str_to_user(iv.interview_date) : __("TBD");
							return `<span class="rdg-ivr" data-tone="${OUT[iv.outcome] || "info"}">${__("R{0}", [iv.round_no])} ${esc(iv.mode || "")} · ${esc(iv.outcome || "")} · ${esc(d)}</span>`;
						})
						.join("");
					return `
						<div class="rdg-sub">
							<div class="rdg-sub-main">
								<div class="rdg-sub-title">${esc(s.requirement_title || s.requirement)}</div>
								<div class="rdg-sub-sub">${client} · ${esc(when)}</div>
								${rounds ? `<div class="rdg-ivrs">${rounds}</div>` : ""}
							</div>
							<span class="rdg-stage" data-tone="${stage.tone}">${esc(stage.label)}</span>
						</div>`;
				})
				.join("")
		);
	}

	render_docs(docs) {
		const esc = frappe.utils.escape_html;
		const $t = this.$root.find(".rdg-docs");
		if (!docs.length) {
			$t.html(`<div class="rdg-muted">${__("No documents uploaded yet.")}</div>`);
			return;
		}
		$t.html(
			docs
				.map((d) => {
					const exp = d.expiry_date
						? ` · ${__("expires {0}", [frappe.datetime.str_to_user(d.expiry_date)])}`
						: "";
					return `
						<div class="rdg-doc">
							<a href="${encodeURI(d.document || "#")}" target="_blank" rel="noopener">${esc(
								d.document_type
							)}</a>
							<span class="rdg-muted">${esc(
								d.uploaded_on ? frappe.datetime.str_to_user(d.uploaded_on) : ""
							)}${esc(exp)}</span>
						</div>`;
				})
				.join("")
		);
	}

	upload_form() {
		const opts = DOC_TYPES.map((t) => `<option value="${frappe.utils.escape_html(t)}">${frappe.utils.escape_html(t)}</option>`).join("");
		return `
			<div class="rdg-upload">
				<select class="rdg-u-type">${opts}</select>
				<input class="rdg-u-expiry" type="date" placeholder="${__("Expiry (optional)")}">
				<input class="rdg-u-file" type="file" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg">
				<button class="rdg-btn rdg-u-go">${__("Upload")}</button>
			</div>
			<div class="rdg-u-hint rdg-muted">${__("PDF, Word, or image · up to 10 MB · only you and recruiters can see it.")}</div>`;
	}

	bind_upload() {
		this.$root.find(".rdg-u-go").on("click", () => {
			const type = this.$root.find(".rdg-u-type").val();
			const expiry = this.$root.find(".rdg-u-expiry").val();
			const fileInput = this.$root.find(".rdg-u-file")[0];
			const file = fileInput && fileInput.files && fileInput.files[0];
			if (!file) {
				frappe.msgprint(__("Choose a file first."));
				return;
			}
			if (file.size > 10 * 1024 * 1024) {
				frappe.msgprint(__("That file is larger than 10 MB."));
				return;
			}
			const reader = new FileReader();
			reader.onload = () => {
				frappe.call({
					method: "racedog_hr.api.upload_my_document",
					args: { document_type: type, file_name: file.name, content: reader.result, expiry_date: expiry || null },
					freeze: true,
					freeze_message: __("Uploading…"),
					callback: () => {
						frappe.show_alert({ message: __("Uploaded"), indicator: "green" }, 4);
						this.reload();
					},
					error: () => frappe.show_alert({ message: __("Upload failed"), indicator: "red" }, 6),
				});
			};
			reader.readAsDataURL(file);
		});
	}

	edit_form(p) {
		const esc = frappe.utils.escape_html;
		return `
			<div class="rdg-edit">
				<label>${__("Available From")}<input class="rdg-e-avail" type="date" value="${esc(
					p.availability_date || ""
				)}"></label>
				<label>${__("Work Auth Expiry")}<input class="rdg-e-visaexp" type="date" value="${esc(
					p.visa_expiry || ""
				)}"></label>
				<label>${__("Phone")}<input class="rdg-e-phone" type="text" value="${esc(
					p.cell_number || ""
				)}"></label>
				<label>${__("Personal Email")}<input class="rdg-e-email" type="email" value="${esc(
					p.personal_email || ""
				)}"></label>
				<label class="rdg-full">${__("Note to my recruiter")}<textarea class="rdg-e-note" rows="2" placeholder="${__(
					"e.g. available two weeks early, newest project was a React migration"
				)}">${esc(p.consultant_note || "")}</textarea></label>
				<button class="rdg-btn rdg-e-save">${__("Save my info")}</button>
			</div>`;
	}

	bind_edit() {
		this.$root.find(".rdg-e-save").on("click", () => {
			const updates = {
				availability_date: this.$root.find(".rdg-e-avail").val() || null,
				visa_expiry: this.$root.find(".rdg-e-visaexp").val() || null,
				cell_number: this.$root.find(".rdg-e-phone").val() || null,
				personal_email: this.$root.find(".rdg-e-email").val() || null,
				consultant_note: this.$root.find(".rdg-e-note").val() || null,
			};
			frappe.call({
				method: "racedog_hr.api.update_my_profile",
				args: { updates: JSON.stringify(updates) },
				freeze: true,
				freeze_message: __("Saving…"),
				callback: () => {
					frappe.show_alert({ message: __("Saved"), indicator: "green" }, 4);
					this.reload();
				},
				error: () => frappe.show_alert({ message: __("Could not save"), indicator: "red" }, 6),
			});
		});
	}
}
