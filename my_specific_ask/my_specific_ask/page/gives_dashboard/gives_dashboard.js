// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

// Gives Dashboard: all members' Gives by industry and by classification.
// The page itself is built by public/js/ask_give_dashboard.js, shared with the other dashboard.
frappe.pages["gives-dashboard"].on_page_load = function (wrapper) {
	frappe.require("/assets/my_specific_ask/js/ask_give_dashboard.js", () => {
		frappe.msa_ask_give_dashboard(wrapper, {
			title: __("Gives Dashboard"),
			table: "Members Give",
			rows_label: __("Gives"),
		});
	});
};

frappe.pages["gives-dashboard"].on_page_show = function (wrapper) {
	wrapper.msa_refresh && wrapper.msa_refresh();
};
