// Color Employee list rows by deployment status (Working/On Bench/Marketing).
frappe.listview_settings["Employee"] = {
	add_fields: ["deployment_status", "hotlist"],
	get_indicator(doc) {
		const map = { Working: "green", "Rolling-Off": "purple", "On Bench": "orange", Marketing: "blue" };
		const s = doc.deployment_status;
		if (!s) return [__("Active"), "gray", "status,=,Active"];
		return [__(s), map[s] || "gray", `deployment_status,=,${s}`];
	},
};
