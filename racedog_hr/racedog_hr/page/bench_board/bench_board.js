// Bench Board — recruiter marketing dashboard. Reads/writes only via the whitelisted
// racedog_hr.api methods, so rate/margin never reaches the client.

frappe.pages["bench-board"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Bench Board"),
		single_column: true,
	});
	page.set_secondary_action(__("Refresh"), () => board.reload(), "refresh");
	const board = new BenchBoard(page);
};

// label -> deployment_status value ("" = default bench view, "All" = everyone)
const STATUS_CHIPS = [
	{ label: "Bench", value: "" },
	{ label: "All", value: "All" },
	{ label: "Working", value: "Working" },
	{ label: "Rolling-Off", value: "Rolling-Off" },
	{ label: "On Bench", value: "On Bench" },
	{ label: "Marketing", value: "Marketing" },
];
const HOTLIST_CHIPS = [
	{ label: "All", value: "" },
	{ label: "Red", value: "Red" },
	{ label: "Orange", value: "Orange" },
	{ label: "Green", value: "Green" },
];

// Advancing to one of these stages prompts for an optional feedback note (audit trail).
const FEEDBACK_STAGES = ["Interview Done", "Offer", "Placed", "Rejected"];

class BenchBoard {
	constructor(page) {
		this.page = page;
		this.state = { search: "", skill: "", visa: "", status: "", hotlist: "" };
		this.requirements = [];
		this.$root = $('<div class="rdg-bench">').appendTo(page.main);
		this.build_shell();
		this.load_filter_options();
		this.reload();
	}

	build_shell() {
		this.$root.html(`
			<div class="rdg-toolbar">
				<input class="rdg-search" type="search" placeholder="${__("Search consultant or skill...")}">
				<select class="rdg-select rdg-f-skill"><option value="">${__("All skills")}</option></select>
				<select class="rdg-select rdg-f-visa"><option value="">${__("All work auth")}</option></select>
			</div>
			<div class="rdg-chiprow rdg-status-chips"></div>
			<div class="rdg-chiprow rdg-hot-chips"><span class="rdg-chiplabel">${__("Hotlist")}</span></div>
			<div class="rdg-grid">
				<div>
					<div class="rdg-col-head">
						<span class="rdg-col-title">${__("Consultants")}</span>
						<span class="rdg-col-count rdg-bench-count"></span>
					</div>
					<div class="rdg-cards"></div>
				</div>
				<div>
					<div class="rdg-col-head">
						<span class="rdg-col-title">${__("Open Requirements")}</span>
						<span class="rdg-col-count rdg-req-count"></span>
					</div>
					<div class="rdg-reqs"></div>
				</div>
				<div>
					<div class="rdg-col-head">
						<span class="rdg-col-title">${__("My Pipeline")}</span>
						<span class="rdg-col-count rdg-pipe-count"></span>
					</div>
					<div class="rdg-pipe"></div>
				</div>
			</div>
		`);

		this.$cards = this.$root.find(".rdg-cards");
		this.$reqs = this.$root.find(".rdg-reqs");
		this.$pipe = this.$root.find(".rdg-pipe");

		const $status = this.$root.find(".rdg-status-chips");
		STATUS_CHIPS.forEach((chip, i) => {
			$(`<button class="rdg-chip${i === 0 ? " is-active" : ""}">${frappe.utils.escape_html(chip.label)}</button>`)
				.on("click", (e) => {
					this.state.status = chip.value;
					$status.find(".rdg-chip").removeClass("is-active");
					$(e.currentTarget).addClass("is-active");
					this.load_bench();
				})
				.appendTo($status);
		});

		const $hot = this.$root.find(".rdg-hot-chips");
		HOTLIST_CHIPS.forEach((chip, i) => {
			const dot = chip.value ? `<span class="rdg-dot" data-hot="${chip.value}"></span>` : "";
			$(`<button class="rdg-chip rdg-hotchip${i === 0 ? " is-active" : ""}">${dot}${frappe.utils.escape_html(chip.label)}</button>`)
				.on("click", (e) => {
					this.state.hotlist = chip.value;
					$hot.find(".rdg-chip").removeClass("is-active");
					$(e.currentTarget).addClass("is-active");
					this.load_bench();
				})
				.appendTo($hot);
		});

		this.$root.find(".rdg-search").on(
			"input",
			frappe.utils.debounce((e) => {
				this.state.search = e.target.value.trim();
				this.load_bench();
			}, 280)
		);
		this.$root.find(".rdg-f-skill").on("change", (e) => {
			this.state.skill = e.target.value;
			this.load_bench();
		});
		this.$root.find(".rdg-f-visa").on("change", (e) => {
			this.state.visa = e.target.value;
			this.load_bench();
		});
	}

	async load_filter_options() {
		try {
			const [skills, visas] = await Promise.all([
				frappe.db.get_list("Skill", { pluck: "name", limit: 0, order_by: "name asc" }),
				frappe.db.get_list("Work Authorization", { pluck: "name", limit: 0, order_by: "name asc" }),
			]);
			const opts = (list) =>
				list.map((v) => `<option value="${frappe.utils.escape_html(v)}">${frappe.utils.escape_html(v)}</option>`).join("");
			this.$root.find(".rdg-f-skill").append(opts(skills));
			this.$root.find(".rdg-f-visa").append(opts(visas));
		} catch (e) {
			// filters are a convenience; the board still works without them.
		}
	}

	reload() {
		this.load_bench();
		this.load_requirements();
		this.load_pipeline();
	}

	load_pipeline() {
		frappe.call({
			method: "racedog_hr.api.get_my_pipeline",
			callback: (r) => this.render_pipeline((r.message && r.message.data) || []),
			error: () => this.render_error(this.$pipe),
		});
	}

	load_bench() {
		this.render_skeletons();
		frappe.call({
			method: "racedog_hr.api.get_bench",
			args: {
				search: this.state.search || null,
				skill: this.state.skill || null,
				visa: this.state.visa || null,
				deployment_status: this.state.status || null,
				hotlist: this.state.hotlist || null,
			},
			callback: (r) => this.render_cards((r.message && r.message.data) || []),
			error: () => this.render_error(this.$cards),
		});
	}

	load_requirements() {
		frappe.call({
			method: "racedog_hr.api.get_open_requirements",
			callback: (r) => {
				this.requirements = (r.message && r.message.data) || [];
				this.render_reqs(this.requirements);
			},
			error: () => this.render_error(this.$reqs),
		});
	}

	render_skeletons() {
		this.$cards.html(Array.from({ length: 6 }, () => '<div class="rdg-skel"></div>').join(""));
	}

	render_error($target) {
		$target.html(
			`<div class="rdg-state is-error"><h4>${__("Could not load")}</h4><p>${__("Please refresh. If this persists, contact your admin.")}</p></div>`
		);
	}

	render_cards(rows) {
		this.$root.find(".rdg-bench-count").text(`${rows.length} ${__("consultant(s)")}`);
		if (!rows.length) {
			this.$cards.html(
				`<div class="rdg-state"><h4>${__("No consultants match")}</h4><p>${__("Adjust the filters, or set a consultant's status from their Employee record.")}</p></div>`
			);
			return;
		}
		this.$cards.empty();
		rows.forEach((row) => this.$cards.append(this.card_html(row)));
	}

	card_html(row) {
		const esc = frappe.utils.escape_html;
		const initials = (row.employee_name || "?")
			.split(" ")
			.map((p) => p[0])
			.slice(0, 2)
			.join("")
			.toUpperCase();
		const avatar = row.image ? `style="background-image:url('${encodeURI(row.image)}')"` : "";
		const email = row.company_email || row.personal_email || "";
		const phone = row.cell_number || "";
		const hot = row.hotlist || "";
		const avail = row.availability_date
			? __("Avail {0}", [frappe.datetime.str_to_user(row.availability_date)])
			: __("Available now");

		const contactBits = [];
		if (email) contactBits.push(esc(email));
		if (phone) contactBits.push(esc(phone));

		const $card = $(`
			<div class="rdg-card" data-hot="${esc(hot)}" draggable="true" data-employee="${esc(row.name)}">
				<div class="rdg-card-top">
					<div class="rdg-avatar" ${avatar}>${avatar ? "" : esc(initials)}</div>
					<div class="rdg-card-head">
						<div class="rdg-name">${esc(row.employee_name || row.name)}
							${hot ? `<span class="rdg-dot" data-hot="${esc(hot)}" title="Hotlist: ${esc(hot)}"></span>` : ""}
						</div>
						<div class="rdg-role">${esc(row.designation || __("Consultant"))}</div>
					</div>
				</div>
				${contactBits.length ? `<div class="rdg-contact">${contactBits.join(" &middot; ")}</div>` : ""}
				${row.current_client ? `<div class="rdg-client">${__("at")} <b>${esc(row.current_client)}</b></div>` : ""}
				<div class="rdg-meta">
					${row.primary_skill ? `<span class="rdg-tag"><b>${esc(row.primary_skill)}</b></span>` : ""}
					${row.visa_status ? `<span class="rdg-tag">${esc(row.visa_status)}</span>` : ""}
				</div>
				<div class="rdg-card-foot">
					<span class="rdg-pill" data-s="${esc(row.deployment_status || "")}">${esc(row.deployment_status || "-")}</span>
					<button class="rdg-btn rdg-market">${__("Market")}</button>
				</div>
				<div class="rdg-avail">${esc(avail)}</div>
			</div>
		`);

		$card.find(".rdg-market").on("click", () => this.open_submit_dialog(row));
		$card.on("dragstart", (e) => {
			e.originalEvent.dataTransfer.setData("text/employee", row.name);
			e.originalEvent.dataTransfer.setData("text/name", row.employee_name || row.name);
			$card.addClass("is-dragging");
		});
		$card.on("dragend", () => $card.removeClass("is-dragging"));
		return $card;
	}

	render_reqs(rows) {
		this.$root.find(".rdg-req-count").text(`${rows.length} ${__("open")}`);
		if (!rows.length) {
			this.$reqs.html(
				`<div class="rdg-state"><h4>${__("No open requirements")}</h4><p>${__("Post one from Client Requirement.")}</p></div>`
			);
			return;
		}
		this.$reqs.empty();
		const esc = frappe.utils.escape_html;
		rows.forEach((req) => {
			const $req = $(`
				<div class="rdg-req" data-req="${esc(req.name)}">
					<div class="rdg-req-title">${esc(req.title || req.name)}</div>
					<div class="rdg-req-sub">
						<span class="rdg-prio" data-p="${esc(req.priority || "Medium")}">${esc(req.priority || "Medium")}</span>
						${req.client ? `<span>${esc(req.client)}</span>` : ""}
						${req.primary_skill ? `<span>${esc(req.primary_skill)}</span>` : ""}
						${req.location ? `<span>${esc(req.location)}</span>` : ""}
					</div>
				</div>
			`);
			$req.on("dragover", (e) => {
				e.preventDefault();
				$req.addClass("is-drop");
			});
			$req.on("dragleave", () => $req.removeClass("is-drop"));
			$req.on("drop", (e) => {
				e.preventDefault();
				$req.removeClass("is-drop");
				const employee = e.originalEvent.dataTransfer.getData("text/employee");
				const name = e.originalEvent.dataTransfer.getData("text/name");
				if (employee) this.create_submission(employee, req.name, name);
			});
			this.$reqs.append($req);
		});
	}

	render_pipeline(rows) {
		this.$root.find(".rdg-pipe-count").text(`${rows.length} ${__("active")}`);
		if (!rows.length) {
			this.$pipe.html(
				`<div class="rdg-state"><h4>${__("No active submissions")}</h4><p>${__(
					"Drag a consultant onto a requirement to start one."
				)}</p></div>`
			);
			return;
		}
		this.$pipe.empty();
		const esc = frappe.utils.escape_html;
		const stages = ["Submitted", "Under Review", "Interview Scheduled", "Interview Done", "Offer", "Placed", "Rejected", "Withdrawn"];
		rows.forEach((s) => {
			const opts = stages
				.map((st) => `<option value="${st}"${st === s.status ? " selected" : ""}>${__(st)}</option>`)
				.join("");
			const $p = $(`
				<div class="rdg-pipecard" data-tone="${esc(s.status)}">
					<div class="rdg-pipe-cand">${esc(s.candidate || s.name)}</div>
					<div class="rdg-pipe-req">${esc(s.requirement_title || s.requirement)}</div>
					<select class="rdg-pipe-stage">${opts}</select>
				</div>
			`);
			$p.find(".rdg-pipe-stage").on("change", (e) => {
				this.update_stage(s.name, e.target.value, s.candidate);
			});
			this.$pipe.append($p);
		});
	}

	update_stage(submission, status, candidate) {
		// Decision stages carry an audit trail — prompt for an optional note.
		if (FEEDBACK_STAGES.includes(status)) {
			const d = new frappe.ui.Dialog({
				title: __("{0} → {1}", [candidate || submission, __(status)]),
				fields: [
					{
						fieldname: "feedback",
						fieldtype: "Small Text",
						label: __("Feedback / notes (optional)"),
					},
				],
				primary_action_label: __("Save"),
				primary_action: (v) => {
					d.hide();
					this._commit_stage(submission, status, candidate, v.feedback || null);
				},
				// Cancel: leave the record unchanged and resync the dropdown.
				secondary_action_label: __("Cancel"),
				secondary_action: () => {
					d.hide();
					this.load_pipeline();
				},
			});
			d.show();
			return;
		}
		this._commit_stage(submission, status, candidate, null);
	}

	_commit_stage(submission, status, candidate, feedback) {
		frappe.call({
			method: "racedog_hr.api.update_submission_status",
			args: { submission, status, feedback },
			freeze: true,
			freeze_message: __("Updating…"),
			callback: (r) => {
				if (r.message && r.message.data) {
					frappe.show_alert(
						{ message: __("{0} → {1}", [candidate || submission, __(status)]), indicator: "green" },
						4
					);
					this.load_pipeline();
				}
			},
			error: () => {
				frappe.show_alert({ message: __("Could not update"), indicator: "red" }, 6);
				this.load_pipeline();
			},
		});
	}

	open_submit_dialog(consultant) {
		if (!this.requirements.length) {
			frappe.msgprint(__("There are no open requirements to submit to yet."));
			return;
		}
		const d = new frappe.ui.Dialog({
			title: __("Submit {0}", [consultant.employee_name || consultant.name]),
			fields: [
				{
					fieldname: "requirement",
					label: __("Requirement"),
					fieldtype: "Select",
					reqd: 1,
					options: this.requirements.map((r) => ({ label: `${r.title} (${r.client || "-"})`, value: r.name })),
				},
			],
			primary_action_label: __("Submit"),
			primary_action: (values) => {
				d.hide();
				this.create_submission(consultant.name, values.requirement, consultant.employee_name);
			},
		});
		d.show();
	}

	create_submission(consultant, requirement, consultantName) {
		frappe.call({
			method: "racedog_hr.api.create_submission",
			args: { consultant, requirement },
			freeze: true,
			freeze_message: __("Submitting..."),
			callback: (r) => {
				if (r.message && r.message.data) {
					frappe.show_alert(
						{ message: __("Submitted {0}", [consultantName || consultant]), indicator: "green" },
						5
					);
					this.load_pipeline();
				}
			},
			error: () => {
				// Double-submission / RTR blocks throw server-side; make sure the
				// recruiter sees it clearly (a blocked drop shouldn't look like a no-op).
				frappe.show_alert(
					{
						message: __("Submission blocked — likely a duplicate or a right-to-represent conflict. See the message."),
						indicator: "red",
					},
					8
				);
			},
		});
	}
}
