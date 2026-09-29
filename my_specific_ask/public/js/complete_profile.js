// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

// A member whose profile still misses required fields (e.g. right after sign-up)
// is taken to that profile from any page until it is saved.
$(document).on("app_ready", () => {
	// app_ready fires while the first route is still loading, so only react to router
	// "change" (fired once a route has rendered) and navigate on the next tick;
	// routing inside that cycle leaves two renders racing and a blank page.
	frappe.router.on("change", () => {
		const profile = frappe.boot.msa_incomplete_profile;
		if (!profile) return;

		const [view, doctype, name] = frappe.get_route();
		if (view === "Form" && doctype === "Members" && name === profile) return;
		setTimeout(() => frappe.set_route("Form", "Members", profile));
	});
});
