// Candidate Pipeline — recruiter/manager view of ONE candidate: every submission
// with its round-by-round interview history and the client feedback per round.
// Feedback here is internal (recruiter/manager) — never exposed to the candidate.

frappe.pages["candidate-pipeline"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Candidate Pipeline"),
		single_column: true,
	});
	const view = new CandidatePipeline(page);
	frappe.pages["candidate-pipeline"].__view = view;
	// Deep-link support: /app/candidate-pipeline?consultant=HR-EMP-00006
	const c = frappe.utils.get_url_arg("consultant");
	if (c) view.load(c);
};

const SUB_TONE = {
	"Submitted": "info",
	"Under Review": "info",
	"Interview Scheduled": "warn",
	"Interview Done": "warn",
	"Offer": "good",
	"Placed": "good",
	"Rejected": "bad",
	"Withdrawn": "muted",
};
const OUTCOME_TONE = {
	Scheduled: "info",
	Cleared: "good",
	Rejected: "bad",
	"On Hold": "warn",
	"No Show": "muted",
};

class CandidatePipeline {
	constructor(page) {
		this.page = page;
		this.$root = $('<div class="rdg-cp">').appendTo(page.main);
		this.build_picker();
		this.$body = $('<div class="rdg-cp-body">').appendTo(this.$root);
		this.$body.html(`<div class="rdg-muted rdg-cp-empty">${__("Pick a consultant to see their full submission + interview history.")}</div>`);
	}

	build_picker() {
		const $bar = $('<div class="rdg-cp-bar">').appendTo(this.$root);
		this.picker = frappe.ui.form.make_control({
			parent: $bar.get(0),
			df: {
				fieldtype: "Link",
				options: "Employee",
				label: __("Consultant"),
				placeholder: __("Search a consultant…"),
				onchange: () => {
					const v = this.picker.get_value();
					if (v) this.load(v);
				},
			},
			render_input: true,
		});
	}

	load(consultant) {
		if (this.picker.get_value() !== consultant) this.picker.set_value(consultant);
		this.$body.html(`<div class="rdg-muted rdg-cp-empty">${__("Loading…")}</div>`);
		frappe.call({
			method: "racedog_hr.api.get_candidate_pipeline",
			args: { consultant },
			callback: (r) => this.render((r.message && r.message.data) || null),
			error: () => this.$body.html(`<div class="rdg-state is-error"><h4>${__("Could not load")}</h4></div>`),
		});
	}

	render(data) {
		const esc = frappe.utils.escape_html;
		if (!data) return;
		const subs = data.submissions || [];
		const header = `
			<div class="rdg-cp-head">
				<h2>${esc(data.candidate || data.consultant)}</h2>
				<span class="rdg-cp-count">${subs.length} ${__("submission(s)")}</span>
			</div>`;
		if (!subs.length) {
			this.$body.html(header + `<div class="rdg-muted rdg-cp-empty">${__("No submissions yet for this consultant.")}</div>`);
			return;
		}
		const html = subs.map((s) => this.submission_block(s, esc)).join("");
		this.$body.html(header + `<div class="rdg-cp-subs">${html}</div>`);
	}

	submission_block(s, esc) {
		const tone = SUB_TONE[s.status] || "info";
		const when = s.submitted_on ? frappe.datetime.str_to_user(s.submitted_on) : "";
		const rounds = (s.interviews || []).map((iv) => this.round_block(iv, esc)).join("");
		const roundsHtml = rounds
			? `<div class="rdg-cp-rounds">${rounds}</div>`
			: `<div class="rdg-muted rdg-cp-norounds">${__("No interview rounds recorded yet.")}</div>`;
		const overall = s.feedback
			? `<div class="rdg-cp-overall"><b>${__("Overall note")}:</b> ${esc(s.feedback)}</div>`
			: "";
		return `
			<div class="rdg-cp-sub">
				<div class="rdg-cp-sub-head">
					<div>
						<div class="rdg-cp-sub-title">${esc(s.requirement_title || s.requirement)}</div>
						<div class="rdg-cp-sub-meta">${s.client ? esc(s.client) + " · " : ""}${__("submitted")} ${esc(when)}</div>
					</div>
					<span class="rdg-stage" data-tone="${tone}">${esc(s.status)}</span>
				</div>
				${roundsHtml}
				${overall}
				<div class="rdg-cp-actions">
					<button class="rdg-btn-sm rdg-add-round" data-sub="${esc(s.name)}">${__("+ Add interview round")}</button>
				</div>
			</div>`;
	}

	round_block(iv, esc) {
		const tone = OUTCOME_TONE[iv.outcome] || "info";
		const when = iv.interview_date ? frappe.datetime.str_to_user(iv.interview_date) : __("TBD");
		const weak = iv.weak_areas
			? `<div class="rdg-cp-weak"><span>${__("Weak areas")}</span>${esc(iv.weak_areas)}</div>`
			: "";
		const fb = iv.client_feedback
			? `<div class="rdg-cp-fb"><span>${__("Client feedback")}</span>${esc(iv.client_feedback)}</div>`
			: `<div class="rdg-muted rdg-cp-nofb">${__("No client feedback yet")}</div>`;
		return `
			<div class="rdg-cp-round" data-tone="${tone}">
				<div class="rdg-cp-round-top">
					<span class="rdg-cp-rn">${__("Round")} ${esc(iv.round_no)}</span>
					<span class="rdg-cp-type">${esc(iv.mode || "")}</span>
					<span class="rdg-cp-when">${esc(when)}</span>
					${iv.interviewer ? `<span class="rdg-cp-panel">${esc(iv.interviewer)}</span>` : ""}
					<span class="rdg-stage rdg-cp-outcome" data-tone="${tone}">${esc(iv.outcome || "")}</span>
				</div>
				${weak}
				${fb}
			</div>`;
	}

	add_round(sub) {
		const d = new frappe.ui.Dialog({
			title: __("Add interview round"),
			fields: [
				{ fieldname: "interview_date", fieldtype: "Datetime", label: __("Date/Time") },
				{ fieldname: "mode", fieldtype: "Select", label: __("Type"), options: "Screening\nTechnical\nManagerial\nClient Round\nHR\nFinal", default: "Technical" },
				{ fieldname: "interviewer", fieldtype: "Data", label: __("Interviewer / Panel") },
				{ fieldname: "outcome", fieldtype: "Select", label: __("Outcome"), options: "Scheduled\nCleared\nRejected\nOn Hold\nNo Show", default: "Scheduled" },
				{ fieldname: "weak_areas", fieldtype: "Small Text", label: __("Weak areas (comma-separated)") },
				{ fieldname: "client_feedback", fieldtype: "Text", label: __("Client feedback (internal — never shown to candidate)") },
			],
			primary_action_label: __("Add round"),
			primary_action: (v) => {
				d.hide();
				frappe.call({
					method: "racedog_hr.api.add_interview",
					args: { submission: sub, ...v },
					freeze: true,
					callback: () => {
						frappe.show_alert({ message: __("Interview round added"), indicator: "green" }, 4);
						this.load(this.picker.get_value());
					},
				});
			},
		});
		d.show();
	}
}

// Delegate the add-round click to the live view instance.
$(document).on("click", ".rdg-cp .rdg-add-round", function () {
	const view = frappe.pages["candidate-pipeline"] && frappe.pages["candidate-pipeline"].__view;
	if (view) view.add_round($(this).data("sub"));
});
