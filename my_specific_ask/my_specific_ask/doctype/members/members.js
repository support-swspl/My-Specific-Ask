// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Members", {
	refresh(frm) {
		if (frm.is_new() || frappe.user.has_role("System Manager")) return;

		if (frm.doc.user === frappe.session.user) {
			frm.set_df_property("user", "read_only", 1);
			// Set by boot_session while required fields are still empty (e.g. after sign-up)
			if (frm.doc.name === frappe.boot.msa_incomplete_profile) {
				frm.set_intro(
					__("Welcome! Please fill in all required fields and click Save to start using My Specific Ask."),
					"yellow"
				);
			}
		} else {
			frm.disable_form();
			frm.set_intro(__("You can view this member. Only your own profile is editable."), "blue");
		}
	},

	after_save(frm) {
		// Saving means every required field is filled: release the redirect in complete_profile.js
		if (frm.doc.name === frappe.boot.msa_incomplete_profile) {
			frappe.boot.msa_incomplete_profile = null;
			frm.set_intro("");
		}
	},
});
