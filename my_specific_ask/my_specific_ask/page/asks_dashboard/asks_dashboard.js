// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

// Asks Dashboard: all members' Asks by industry and by classification.
// The page itself is built by public/js/ask_give_dashboard.js, shared with the other dashboard.
frappe.pages["asks-dashboard"].on_page_load = function (wrapper) {
	frappe.require("/assets/my_specific_ask/js/ask_give_dashboard.js", () => {
		frappe.msa_ask_give_dashboard(wrapper, {
			title: __("Asks Dashboard"),
			table: "Members Ask",
			rows_label: __("Asks"),
		});
	});
};

frappe.pages["asks-dashboard"].on_page_show = function (wrapper) {
	wrapper.msa_refresh && wrapper.msa_refresh();
};
