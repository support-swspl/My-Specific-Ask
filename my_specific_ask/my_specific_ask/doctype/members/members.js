// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Members", {
	refresh(frm) {
		if (frm.is_new() || frappe.user.has_role("System Manager")) return;

		if (frm.doc.user === frappe.session.user) {
			frm.set_df_property("user", "read_only", 1);
		} else {
			frm.disable_form();
			frm.set_intro(__("You can view this member. Only your own profile is editable."), "blue");
		}
	},
});
