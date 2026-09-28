# Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

MEMBER_ROLE = "Specific Ask Member"
READ_PTYPES = ("read", "select", "print", "report", "email", "export")


class Members(Document):
	def validate(self):
		# Members may edit their own profile but not hand it to another login
		if not self.is_new() and not is_admin() and self.has_value_changed("user"):
			frappe.throw(_("Only a System Manager can change the linked User."))


def is_admin(user=None):
	return "System Manager" in frappe.get_roles(user)


def has_permission(doc, ptype=None, user=None):
	"""Everyone with read access sees all members; only the linked user can modify a profile."""
	user = user or frappe.session.user
	if ptype in READ_PTYPES or is_admin(user):
		return None
	if doc.user != user:
		return False
	return None


def create_member_users(send_welcome_email=0):
	"""Create a login for every Member without one, using the Member's email.

	bench --site <site> execute my_specific_ask.my_specific_ask.doctype.members.members.create_member_users
	"""
	created, linked, skipped = 0, 0, []
	for m in frappe.get_all("Members", filters={"user": ["is", "not set"]}, fields=["name", "full_name", "email"]):
		email = (m.email or "").strip().lower()
		if not email or frappe.db.exists("Members", {"user": email}):
			skipped.append(m.name)
			continue

		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
		else:
			user = frappe.get_doc({
				"doctype": "User",
				"email": email,
				"first_name": m.full_name,
				"user_type": "System User",
				"send_welcome_email": int(send_welcome_email),
			})
			user.insert(ignore_permissions=True)
			created += 1
		user.add_roles(MEMBER_ROLE)

		frappe.db.set_value("Members", m.name, "user", email)
		linked += 1

	frappe.db.commit()
	return {"created": created, "linked": linked, "skipped": skipped}
