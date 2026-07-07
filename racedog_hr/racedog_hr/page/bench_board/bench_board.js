// Bench Board — recruiter marketing board. Reads/writes only via the whitelisted
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

const BENCH_STATUSES = ["On Bench", "Marketing", "Interviewing", "Rolling-Off"];

class BenchBoard {
	constructor(page) {
		this.page = page;
		this.state = { search: "", skill: "", visa: "", status: "" };
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
			<div class="rdg-chips"></div>
			<div class="rdg-grid">
				<div>
					<div class="rdg-col-head">
						<span class="rdg-col-title">${__("Bench")}</span>
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
			</div>
		`);

		this.$cards = this.$root.find(".rdg-cards");
		this.$reqs = this.$root.find(".rdg-reqs");

		// status chips
		const $chips = this.$root.find(".rdg-chips");
		["", ...BENCH_STATUSES].forEach((status) => {
			const label = status || __("All");
			$(`<button class="rdg-chip${status === "" ? " is-active" : ""}">${frappe.utils.escape_html(label)}</button>`)
				.on("click", (e) => {
					this.state.status = status;
					$chips.find(".rdg-chip").removeClass("is-active");
					$(e.currentTarget).addClass("is-active");
					this.load_bench();
				})
				.appendTo($chips);
		});

		// search (debounced) + selects
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
			const opts = (list) => list.map((v) => `<option value="${frappe.utils.escape_html(v)}">${frappe.utils.escape_html(v)}</option>`).join("");
			this.$root.find(".rdg-f-skill").append(opts(skills));
			this.$root.find(".rdg-f-visa").append(opts(visas));
		} catch (e) {
			// filters are a convenience; the board still works without them.
		}
	}

	reload() {
		this.load_bench();
		this.load_requirements();
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
		$target.html(`<div class="rdg-state is-error"><h4>${__("Could not load")}</h4><p>${__("Please refresh. If this persists, contact your admin.")}</p></div>`);
	}

	render_cards(rows) {
		this.$root.find(".rdg-bench-count").text(`${rows.length} ${__("consultant(s)")}`);
		if (!rows.length) {
			this.$cards.html(`<div class="rdg-state"><h4>${__("No one on the bench matches")}</h4><p>${__("Adjust the filters, or mark a consultant On Bench from their Employee record.")}</p></div>`);
			return;
		}
		this.$cards.empty();
		rows.forEach((row) => this.$cards.append(this.card_html(row)));
	}

	card_html(row) {
		const initials = (row.employee_name || "?")
			.split(" ")
			.map((p) => p[0])
			.slice(0, 2)
			.join("")
			.toUpperCase();
		const avatar = row.image
			? `style="background-image:url('${encodeURI(row.image)}')"`
			: "";
		const esc = frappe.utils.escape_html;
		const avail = row.availability_date
			? __("Avail {0}", [frappe.datetime.str_to_user(row.availability_date)])
			: __("Available now");

		const $card = $(`
			<div class="rdg-card" draggable="true" data-employee="${esc(row.name)}">
				<div class="rdg-card-top">
					<div class="rdg-avatar" ${avatar}>${avatar ? "" : esc(initials)}</div>
					<div>
						<div class="rdg-name">${esc(row.employee_name || row.name)}</div>
						<div class="rdg-role">${esc(row.designation || __("Consultant"))}</div>
					</div>
				</div>
				<div class="rdg-meta">
					${row.primary_skill ? `<span class="rdg-tag"><b>${esc(row.primary_skill)}</b></span>` : ""}
					${row.visa_status ? `<span class="rdg-tag">${esc(row.visa_status)}</span>` : ""}
				</div>
				<div class="rdg-card-foot">
					<span class="rdg-pill" data-s="${esc(row.deployment_status || "")}">${esc(row.deployment_status || "-")}</span>
					<button class="rdg-btn rdg-market">${__("Market")}</button>
				</div>
				<div class="rdg-avail" style="margin-top:8px">${esc(avail)}</div>
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
			this.$reqs.html(`<div class="rdg-state"><h4>${__("No open requirements")}</h4><p>${__("Post one from Client Requirement.")}</p></div>`);
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
				if (employee) this.create_submission(employee, req.name, name, req.title);
			});
			this.$reqs.append($req);
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

	create_submission(consultant, requirement, consultantName, reqTitle) {
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
				}
			},
			// double-submission / RTR blocks surface as a normal server error dialog.
		});
	}
}
