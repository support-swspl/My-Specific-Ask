# Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Desk access for member logins.

Members (MEMBER_ROLE) only see the My Specific Ask workspace and the Members list;
every other module is blocked. MANAGER gets every role.
"""

import frappe
from frappe.permissions import AUTOMATIC_ROLES, add_permission
from frappe.utils import get_url

MEMBER_ROLE = "Specific Ask Member"
ADMIN_ROLE = "System Manager"
MANAGER = "milind@swspl.com"
APP_MODULE = "My Specific Ask"
WORKSPACE = "My Specific Ask"
MODULE_PROFILE = "Specific Ask Member"

# Link targets on the Members form: members need to pick values, not browse them
LINKED_DOCTYPES = ("Network Type", "Power Team")

EMAIL_TEMPLATE = "Member Welcome"
WELCOME_EMAIL_HTML = """<p>Dear {{ first_name }},</p>

<p>Welcome to <b>My Specific Ask</b>, the 1-2-1 match making platform for our members.
Your member account is ready.</p>

<p>Your login ID: <b>{{ user }}</b></p>

<p>Please click the button below to set your password:</p>

<p><a href="{{ link }}" style="display:inline-block;padding:10px 20px;background:#171717;color:#ffffff;
text-decoration:none;border-radius:6px;font-weight:600;">Set Your Password</a></p>

<p style="font-size:12px;color:#6b7280;">Or copy this link into your browser:<br>{{ link }}</p>

<p>After setting your password, log in at <a href="{{ login_url }}">{{ login_url }}</a>.
For your security, every login will also ask for a verification code that we send to this email address.</p>

<p>In My Specific Ask you can view all members and update your own profile, Gives and Asks.</p>

<p>If this link has expired, click <b>Forgot Password</b> on the login page to get a new one.</p>

<p>Regards,<br>Milind Lokare<br>My Specific Ask</p>
"""

LOGIN_EMAIL_TEMPLATE = "Member Login Welcome"
LOGIN_EMAIL_HTML = """<p>Dear {{ first_name }},</p>

<p>Welcome to <b>My Specific Ask</b>! You have logged in successfully.</p>

<p>Here you can:</p>
<ul>
<li>View the profiles of all members</li>
<li>Keep your own profile, Gives and Asks up to date</li>
</ul>

<p>Log in any time at <a href="{{ login_url }}">{{ login_url }}</a> with your login ID <b>{{ user }}</b>.</p>

<p>Regards,<br>Milind Lokare<br>My Specific Ask</p>
"""


def setup():
	"""after_migrate hook; safe to run repeatedly."""
	ensure_member_role()
	grant_link_select()
	ensure_workspace()
	ensure_desktop_icon()
	ensure_module_profile()
	ensure_email_template()
	ensure_signup()
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
		# Custom DocPerm defaults read/export to 1, which would let members open and export the list
		for name in frappe.get_all("Custom DocPerm", filters={"parent": doctype, "role": MEMBER_ROLE}, pluck="name"):
			frappe.db.set_value("Custom DocPerm", name, {"read": 0, "export": 0, "select": 1})
		frappe.clear_cache(doctype=doctype)


def ensure_workspace():
	# No `app` on the workspace: migrate deletes public workspaces that have an app but no JSON file in it
	if frappe.db.exists("Workspace", WORKSPACE):
		frappe.db.set_value("Workspace", WORKSPACE, "app", None)
		return
	frappe.get_doc({
		"doctype": "Workspace",
		"label": WORKSPACE,
		"title": WORKSPACE,
		"module": APP_MODULE,
		"public": 1,
		"icon": "users",
		"content": frappe.as_json([
			{"id": "msa_header", "type": "header", "data": {"text": f"<span class=\"h4\"><b>{WORKSPACE}</b></span>", "col": 12}},
			{"id": "msa_members", "type": "shortcut", "data": {"shortcut_name": "Members", "col": 3}},
		]),
		"shortcuts": [{"type": "DocType", "link_to": "Members", "label": "Members", "doc_view": "List"}],
		"roles": [{"role": MEMBER_ROLE}, {"role": ADMIN_ROLE}],
	}).insert(ignore_permissions=True)


def ensure_desktop_icon():
	"""v16 desk home shows an icon only when its Workspace Sidebar has an item the user can open."""
	if not frappe.db.exists("Workspace Sidebar", WORKSPACE):
		frappe.get_doc({
			"doctype": "Workspace Sidebar",
			"title": WORKSPACE,
			"app": "my_specific_ask",
			"module": APP_MODULE,
			"header_icon": "users",
			"items": [
				{"label": "Home", "type": "Link", "link_type": "Workspace", "link_to": WORKSPACE, "icon": "home"},
				{"label": "Members", "type": "Link", "link_type": "DocType", "link_to": "Members", "icon": "users"},
			],
		}).insert(ignore_permissions=True)

	if not frappe.db.exists("Desktop Icon", WORKSPACE):
		frappe.get_doc({
			"doctype": "Desktop Icon",
			"label": WORKSPACE,
			"icon_type": "Link",
			"link_type": "Workspace Sidebar",
			"link_to": WORKSPACE,
			"icon": "users",
			"standard": 1,
		}).insert(ignore_permissions=True)

	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")


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


def ensure_email_template():
	"""One email for new logins and password resets: welcome text plus the set-password link.

	Created once; edit the wording later in Email Template > Member Welcome.
	"""
	if not frappe.db.exists("Email Template", EMAIL_TEMPLATE):
		frappe.get_doc({
			"doctype": "Email Template",
			"__newname": EMAIL_TEMPLATE,
			"subject": "Welcome to My Specific Ask - set your password",
			"use_html": 1,
			"response_html": WELCOME_EMAIL_HTML,
		}).insert(ignore_permissions=True)

	if not frappe.db.exists("Email Template", LOGIN_EMAIL_TEMPLATE):
		frappe.get_doc({
			"doctype": "Email Template",
			"__newname": LOGIN_EMAIL_TEMPLATE,
			"subject": "Welcome to My Specific Ask",
			"use_html": 1,
			"response_html": LOGIN_EMAIL_HTML,
		}).insert(ignore_permissions=True)

	settings = frappe.get_single("System Settings")
	changed = False
	if not settings.welcome_email_template or not settings.reset_password_template:
		settings.welcome_email_template = settings.welcome_email_template or EMAIL_TEMPLATE
		settings.reset_password_template = settings.reset_password_template or EMAIL_TEMPLATE
		changed = True
	# The welcome link uses the reset expiry; Frappe's 20-minute default is too short for invitations
	if int(settings.reset_password_link_expiry_duration or 0) == 1200:
		settings.reset_password_link_expiry_duration = 3 * 24 * 60 * 60
		changed = True
	if changed:
		settings.save(ignore_permissions=True)


def ensure_signup():
	"""Open self sign-up when the site config has msa_open_signup = 1; sign-ups become members."""
	if not frappe.conf.get("msa_open_signup"):
		return
	frappe.db.set_single_value("Website Settings", "disable_signup", 0)
	frappe.db.set_single_value("Portal Settings", "default_role", MEMBER_ROLE)


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


def send_login_welcome(login_manager):
	"""on_login hook (runs after 2FA): welcome email on a member's first successful login."""
	user = login_manager.user
	if user in (MANAGER, "Administrator") or MEMBER_ROLE not in frappe.get_roles(user):
		return

	sent_key = f"msa_login_welcome_sent:{user}"
	if frappe.db.get_default(sent_key):
		return
	frappe.db.set_default(sent_key, 1)
	frappe.enqueue(
		"my_specific_ask.access.send_login_welcome_mail", queue="short", user=user, enqueue_after_commit=True
	)


def send_login_welcome_mail(user):
	if not frappe.db.exists("Email Template", LOGIN_EMAIL_TEMPLATE):
		return
	user_doc = frappe.get_doc("User", user)
	email = frappe.get_doc("Email Template", LOGIN_EMAIL_TEMPLATE).get_formatted_email({
		"first_name": user_doc.first_name or user_doc.full_name,
		"user": user,
		"login_url": get_url(),
	})
	frappe.sendmail(
		recipients=user_doc.email,
		subject=email["subject"],
		content=email["message"],
		with_container=True,
		delayed=False,
	)


def ensure_member_profile(doc, method=None):
	"""User on_update hook: every member login gets its own Members record.

	Links a Members record with the same email if one is waiting, else creates a draft
	(e.g. after self sign-up) that the member completes on first save.
	"""
	roles = {r.role for r in doc.roles}
	if doc.name == MANAGER or MEMBER_ROLE not in roles or ADMIN_ROLE in roles:
		return
	if frappe.db.exists("Members", {"user": doc.name}):
		return

	waiting = frappe.db.get_value("Members", {"email": doc.email, "user": ["is", "not set"]}, "name")
	if waiting:
		frappe.db.set_value("Members", waiting, "user", doc.name)
		return

	member = frappe.get_doc({
		"doctype": "Members",
		"full_name": doc.full_name or doc.first_name,
		"email": doc.email,
		"user": doc.name,
		"status": "Active",
		"country": "India",
		"members_country": "India",
	})
	member.flags.ignore_mandatory = True
	member.insert(ignore_permissions=True)


def get_incomplete_profile(user):
	"""Name of the member's own Members profile while it still misses required fields, else None."""
	roles = frappe.get_roles(user)
	if user in (MANAGER, "Administrator") or ADMIN_ROLE in roles or MEMBER_ROLE not in roles:
		return None
	profile = frappe.db.get_value("Members", {"user": user}, "name")
	if profile and frappe.get_doc("Members", profile)._get_missing_mandatory_fields():
		return profile
	return None


def boot_session(bootinfo):
	"""boot_session hook: tells complete_profile.js which profile the member must finish first."""
	bootinfo.msa_incomplete_profile = get_incomplete_profile(frappe.session.user)


def refresh_member_boot(doc, method=None):
	"""Members on_update: drop the member's cached boot and home page so the redirect stops once saved."""
	if doc.user:
		frappe.cache.hdel("bootinfo", doc.user)
		frappe.cache.hdel("home_page", doc.user)


def profile_url(profile):
	return f"/desk/members/{profile}"


def send_to_incomplete_profile(login_manager):
	"""on_login hook: after login, a member with an unfinished profile lands straight on it."""
	if profile := get_incomplete_profile(login_manager.user):
		# The login page goes to get_home_page(), which returns this cached value first
		frappe.cache.hset("home_page", login_manager.user, profile_url(profile).lstrip("/"))


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_password(
	new_password: str, logout_all_sessions: int = 0, key: str | None = None, old_password: str | None = None
):
	"""Frappe's update_password (set-password page), but a member with an unfinished profile
	is sent to it instead of /desk."""
	from frappe.core.doctype.user.user import update_password as frappe_update_password

	redirect = frappe_update_password(
		new_password, logout_all_sessions=logout_all_sessions, key=key, old_password=old_password
	)
	if frappe.session.user != "Guest" and (profile := get_incomplete_profile(frappe.session.user)):
		return profile_url(profile)
	return redirect


def user_validate(doc, method=None):
	"""User validate hook: member logins always carry the member module profile and workspace."""
	# Self sign-up inserts the user with a random password, then saves again to add the role;
	# Frappe re-applies that password on the second save and mails a "password changed" alert.
	# Only sign-up saves an existing User as Guest, so drop the stale password there.
	if frappe.session.user == "Guest" and not doc.is_new():
		doc._User__new_password = None

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
