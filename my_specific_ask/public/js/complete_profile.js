// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

// A member whose profile still misses required fields (e.g. right after sign-up)
// is taken to that profile from any page until it is saved.
$(document).on("app_ready", () => {
	const go_to_profile = () => {
		const profile = frappe.boot.msa_incomplete_profile;
		if (!profile) return;

		const [view, doctype, name] = frappe.get_route();
		if (view === "Form" && doctype === "Members" && name === profile) return;
		frappe.set_route("Form", "Members", profile);
	};

	go_to_profile();
	frappe.router.on("change", go_to_profile);
});
