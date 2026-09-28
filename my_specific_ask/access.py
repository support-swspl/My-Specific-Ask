# Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Desk access for member logins.

Members (MEMBER_ROLE) only see the My Specific Ask workspace and the Members list;
every other module is blocked. MANAGER gets every role.
"""

import frappe
from frappe.permissions import AUTOMATIC_ROLES, add_permission

MEMBER_ROLE = "Specific Ask Member"
ADMIN_ROLE = "System Manager"
MANAGER = "milind@swspl.com"
APP_MODULE = "My Specific Ask"
WORKSPACE = "My Specific Ask"
MODULE_PROFILE = "Specific Ask Member"

# Link targets on the Members form: members need to pick values, not browse them
LINKED_DOCTYPES = ("Network Type", "Power Team")


def setup():
	"""after_migrate hook; safe to run repeatedly."""
	ensure_member_role()
	grant_link_select()
	ensure_workspace()
	ensure_module_profile()
	setup_manager()

	for user in frappe.get_all("Has Role", filters={"role": MEMBER_ROLE, "parenttype": "User"}, pluck="parent"):
		if user != MANAGER:
			frappe.get_doc("User", user).save(ignore_permissions=True)  # enforced in user_validate

	frappe.db.commit()


def ensure_member_role():
	if not frappe.db.exists("Role", MEMBER_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": MEMBER_ROLE, "desk_access": 1}).insert()
	frappe.db.set_value("Role", MEMBER_ROLE, "desk_access", 1)


def grant_link_select():
	for doctype in LINKED_DOCTYPES:
		if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": MEMBER_ROLE, "permlevel": 0}):
			add_permission(doctype, MEMBER_ROLE, 0, "select")


def ensure_workspace():
	if frappe.db.exists("Workspace", WORKSPACE):
		return
	frappe.get_doc({
		"doctype": "Workspace",
		"label": WORKSPACE,
		"title": WORKSPACE,
		"module": APP_MODULE,
		"app": "my_specific_ask",
		"public": 1,
		"icon": "users",
		"content": frappe.as_json([
			{"id": "msa_header", "type": "header", "data": {"text": f"<span class=\"h4\"><b>{WORKSPACE}</b></span>", "col": 12}},
			{"id": "msa_members", "type": "shortcut", "data": {"shortcut_name": "Members", "col": 3}},
		]),
		"shortcuts": [{"type": "DocType", "link_to": "Members", "label": "Members", "doc_view": "List"}],
		"roles": [{"role": MEMBER_ROLE}, {"role": ADMIN_ROLE}],
	}).insert(ignore_permissions=True)


def ensure_module_profile():
	"""Block every module except this app's; refreshed on each migrate so new apps stay hidden."""
	blocked = [m for m in frappe.get_all("Module Def", pluck="name") if m != APP_MODULE]
	if frappe.db.exists("Module Profile", MODULE_PROFILE):
		profile = frappe.get_doc("Module Profile", MODULE_PROFILE)
	else:
		profile = frappe.new_doc("Module Profile")
		profile.module_profile_name = MODULE_PROFILE
	profile.set("block_modules", [{"module": m} for m in sorted(blocked)])
	profile.save(ignore_permissions=True)


def setup_manager():
	if frappe.db.exists("User", MANAGER):
		user = frappe.get_doc("User", MANAGER)
	else:
		user = frappe.get_doc({
			"doctype": "User",
			"email": MANAGER,
			"first_name": "Milind",
			"user_type": "System User",
			"send_welcome_email": 1,
		})
		user.insert(ignore_permissions=True)

	# Every role except the member role, which carries member-only 2FA
	all_roles = frappe.get_all(
		"Role", filters={"disabled": 0, "name": ["not in", (*AUTOMATIC_ROLES, MEMBER_ROLE)]}, pluck="name"
	)
	missing = set(all_roles) - {r.role for r in user.roles}
	if missing or user.module_profile or user.block_modules or user.user_type != "System User":
		user.user_type = "System User"
		user.module_profile = None
		user.set("block_modules", [])
		for role in sorted(missing):
			user.append("roles", {"role": role})
		user.save(ignore_permissions=True)

	for admin in (MANAGER, "Administrator"):
		frappe.get_doc("User", admin).remove_roles(MEMBER_ROLE)


def user_validate(doc, method=None):
	"""User validate hook: member logins always carry the member module profile and workspace."""
	roles = {r.role for r in doc.roles}
	if doc.name == MANAGER or MEMBER_ROLE not in roles or ADMIN_ROLE in roles:
		return
	if not frappe.db.exists("Module Profile", MODULE_PROFILE):
		return

	doc.module_profile = MODULE_PROFILE
	blocked = frappe.get_all("Block Module", filters={"parent": MODULE_PROFILE, "parenttype": "Module Profile"}, pluck="module")
	doc.set("block_modules", [{"module": m} for m in blocked])
	if frappe.db.exists("Workspace", WORKSPACE):
		doc.default_workspace = WORKSPACE
