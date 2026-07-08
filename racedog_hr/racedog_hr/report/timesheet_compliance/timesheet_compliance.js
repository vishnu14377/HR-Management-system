// Timesheet Compliance — HR's month-end "who's still missing" view.
// Defaults the period to last month (the one currently owed) and colors Missing red.

frappe.query_reports["Timesheet Compliance"] = {
	filters: [
		{
			fieldname: "period",
			label: __("Period (YYYY-MM)"),
			fieldtype: "Data",
			reqd: 1,
			default: frappe.datetime.add_months(frappe.datetime.month_start(), -1).slice(0, 7),
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "Status" || column.label === "Status") {
			const colors = {
				Missing: "#e5484d",
				Rejected: "#f5a524",
				Submitted: "#1f5fa8",
				"Under Review": "#a5731a",
				Approved: "#3f7a1e",
			};
			const c = colors[data && data.Status];
			if (c) value = `<span style="color:${c};font-weight:600">${value}</span>`;
		}
		return value;
	},
};
