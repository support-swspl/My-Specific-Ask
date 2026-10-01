# Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

import re
from email.utils import formataddr

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html, get_fullname, get_link_to_form, get_url

MEMBER_ROLE = "Specific Ask Member"
READ_PTYPES = ("read", "select", "print", "report", "email", "export")
APP_TITLE = "My Specific Ask"
# Gives a member must have in their own profile before they can request a 1-2-1
MIN_GIVES = 5

ONE_TO_ONE_EMAIL_HTML = """<p>Dear {{ target.full_name }},</p>

<p>{{ intro }}</p>

<p>Please get in touch with them to fix a time.</p>

<table cellpadding="0" cellspacing="0" style="width:100%;max-width:520px;border:1px solid #e5e7eb;border-radius:6px;border-collapse:separate;font-size:14px;">
{% for heading, rows in details %}
<tr><td colspan="2" style="padding:10px 14px;background:#f3f4f6;font-weight:600;color:#171717;">{{ heading }}</td></tr>
{% for label, value in rows %}{% if value %}
<tr>
<td style="padding:8px 14px;width:40%;color:#6b7280;border-top:1px solid #e5e7eb;">{{ label }}</td>
<td style="padding:8px 14px;color:#171717;border-top:1px solid #e5e7eb;">{{ value }}</td>
</tr>
{% endif %}{% endfor %}
{% endfor %}
</table>

<p>Regards,<br>{{ me.full_name }}</p>

<p style="font-size:12px;color:#6b7280;">Powered by <a href="{{ login_url }}" style="color:#6b7280;">My Specific Ask</a></p>
"""


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
		return True
	if doc.user != user:
		return False
	return True


def get_requester(user):
	"""The profile of the user asking for a 1-2-1 and the detail sections sent along with the request."""
	profile = frappe.db.get_value("Members", {"user": user}, "name")
	if not profile:
		# Admins without a profile are introduced by name and email only
		me = frappe._dict(full_name=get_fullname(user), email=user)
		return me, [(_("Contact"), [(_("Email"), me.email)])]

	me = frappe.get_doc("Members", profile)
	details = [
		(_("Contact"), [
			(_("Phone"), me.mobile_number),
			(_("Email"), me.email),
		]),
		(_("Networking Details"), [
			(_("Network"), frappe.db.get_value("Network Type", me.network, "network_name") or me.network),
			(_("Chapter"), me.chapter_name),
			(_("Region"), me.region),
		]),
		(_("Category"), [
			(_("Category"), me.category),
			(_("Industry"), me.industry__segment),
		]),
	]
	# Drop a section when the profile has none of its fields filled
	return me, [(heading, rows) for heading, rows in details if any(value for _label, value in rows)]


def one_to_one_intro(me):
	if me.get("company_name"):
		return _("{0} from {1} would like to do a 1-2-1.").format(me.full_name, me.company_name)
	return _("{0} would like to do a 1-2-1.").format(me.full_name)


@frappe.whitelist(methods=["POST"])
def request_one_to_one(member: str):
	"""Email `member` a 1-2-1 request from the logged-in user and add it to that user's ToDo list.

	The ToDo is a plain self-assigned one with no reference document, so no bell
	notification is raised and nothing is written on the other member's profile.
	"""
	from frappe.email.doctype.email_account.email_account import EmailAccount

	target = frappe.get_doc("Members", member)
	target.check_permission("read")

	user = frappe.session.user
	if target.user == user:
		frappe.throw(_("You cannot request a 1-2-1 with yourself."))
	if not target.email:
		frappe.throw(_("{0} has no email address.").format(target.full_name))

	me, details = get_requester(user)
	# The reports check this before asking; enforced here too so no request can skip it
	if not has_enough_gives(me):
		frappe.throw(not_enough_gives_message(me), title=_("Add more Gives"))
	intro = one_to_one_intro(me)

	# Mail goes out under the app's name; without this the sender shows as the email account's name
	account = EmailAccount.find_default_outgoing()
	sender = formataddr((APP_TITLE, account.email_id)) if account and account.email_id else None

	frappe.sendmail(
		recipients=target.email,
		sender=sender,
		reply_to=me.email,
		subject=intro.rstrip("."),
		message=frappe.render_template(
			ONE_TO_ONE_EMAIL_HTML,
			{"target": target, "me": me, "intro": intro, "details": details, "login_url": get_url()},
		),
		with_container=True,
		delayed=False,
	)

	frappe.get_doc({
		"doctype": "ToDo",
		"allocated_to": user,
		"assigned_by": user,
		"description": _("Do a 1-2-1 with {0} ({1})").format(
			get_link_to_form("Members", target.name, escape_html(target.full_name)),
			escape_html(target.company_name or ""),
		),
	}).insert()

	# The member who was asked gets a follow-up ToDo and a bell notification, when they have a login
	if target.user:
		my_name = escape_html(me.full_name)
		if me.get("name"):
			my_name = get_link_to_form("Members", me.name, my_name)
		follow_up = frappe.get_doc({
			"doctype": "ToDo",
			"allocated_to": target.user,
			"assigned_by": user,
			"description": _("Follow up: {0} ({1}) has requested a 1-2-1 with you.").format(
				my_name, escape_html(me.get("company_name") or "")
			),
		}).insert()

		# "Alert" notifications are bell-only: the request email above is the only mail sent
		frappe.get_doc({
			"doctype": "Notification Log",
			"type": "Alert",
			"for_user": target.user,
			"from_user": user,
			"subject": _("{0} has requested a 1-2-1 with you. Please follow up.").format(
				frappe.bold(escape_html(me.full_name))
			),
			"document_type": "ToDo",
			"document_name": follow_up.name,
		}).insert(ignore_permissions=True)

	return target.full_name


@frappe.whitelist()
def get_total_gives(filters=None):
	"""Number card on the home page: Gives across all members."""
	frappe.has_permission("Members", throw=True)
	return {"value": frappe.db.count("Members Give", {"parenttype": "Members"}), "fieldtype": "Int"}


@frappe.whitelist()
def get_total_asks(filters=None):
	"""Number card on the home page: Asks across all members."""
	frappe.has_permission("Members", throw=True)
	return {"value": frappe.db.count("Members Ask", {"parenttype": "Members"}), "fieldtype": "Int"}


def count_gives(me):
	return frappe.db.count("Members Give", {"parent": me.name, "parenttype": "Members"}) if me.get("name") else 0


def has_enough_gives(me):
	"""A member must have listed MIN_GIVES Gives before asking for a 1-2-1.
	Logins without a member profile (admins) have no Gives to list and are not held to it."""
	return not me.get("name") or count_gives(me) >= MIN_GIVES


def not_enough_gives_message(me):
	return _(
		"You need at least {0} Gives in your profile before you can request a 1-2-1. You have {1} now. "
		"Please add more Gives to your member profile and try again."
	).format(MIN_GIVES, count_gives(me))


@frappe.whitelist()
def get_one_to_one_info():
	"""What the report buttons need about the logged-in user: whether they may request a 1-2-1,
	and their request as WhatsApp text - the email's content, without the greeting
	(the report adds "Hi <member>," for the row that was clicked)."""
	me, details = get_requester(frappe.session.user)
	if not has_enough_gives(me):
		return {"allowed": False, "message": not_enough_gives_message(me)}

	lines = [one_to_one_intro(me), "", _("Please get in touch to fix a time."), ""]
	for heading, rows in details:
		lines.append(f"*{heading}*")
		lines += [f"{label}: {value}" for label, value in rows if value]
		lines.append("")
	lines += [_("Regards,"), me.full_name, "", _("Powered by My Specific Ask")]
	return {"allowed": True, "whatsapp_text": "\n".join(lines)}


# Last column of the Search Gives / Search Asks reports. It carries the member's mobile
# number, which the report script turns into the WhatsApp button.
ACTIONS_COLUMN = "m.mobile_number as \"Actions:Data:210\""

# Search Gives / Search Asks report script: "Request 1-2-1" (email) and WhatsApp buttons on every row
ONE_TO_ONE_REPORT_JS = """// Whether the logged-in member may request a 1-2-1 (enough Gives) and their WhatsApp message.
// Loaded up front and again each time a report opens: opening WhatsApp from inside a server
// callback would be stopped by the browser's pop-up blocker.
frappe.msa_load_one_to_one = () =>
	frappe.call("my_specific_ask.my_specific_ask.doctype.members.members.get_one_to_one_info").then((r) => {
		frappe.msa_one_to_one = r.message;
	});
frappe.msa_load_one_to_one();

// Pop-up when the member has too few Gives; true when the request may go ahead
frappe.msa_can_request_one_to_one = () => {
	const info = frappe.msa_one_to_one;
	if (!info) {
		frappe.show_alert({ message: __("Still loading, please try again."), indicator: "orange" });
		return false;
	}
	if (!info.allowed) {
		frappe.msgprint({ title: __("Add more Gives"), indicator: "orange", message: info.message });
		// They may add Gives and come straight back
		frappe.msa_load_one_to_one();
		return false;
	}
	return true;
};

frappe.msa_request_one_to_one = (button) => {
	if (!frappe.msa_can_request_one_to_one()) return;
	const { member, memberName } = button.dataset;
	frappe.confirm(__("Send a 1-2-1 request to {0}?", [frappe.utils.escape_html(memberName).bold()]), () => {
		frappe.call({
			method: "my_specific_ask.my_specific_ask.doctype.members.members.request_one_to_one",
			args: { member },
			freeze: true,
			freeze_message: __("Sending request..."),
			callback: () =>
				frappe.show_alert({
					message: __("1-2-1 request emailed and added to your <a href='/desk/todo'>ToDo list</a>."),
					indicator: "green",
				}),
		});
	});
};

frappe.msa_whatsapp_one_to_one = (button) => {
	if (!frappe.msa_can_request_one_to_one()) return;
	const { phone, mobile, memberName } = button.dataset;
	if (!phone) {
		// Say what is stored instead of opening WhatsApp with no chat selected
		frappe.msgprint({
			title: __("No WhatsApp number"),
			indicator: "orange",
			message: mobile
				? __("The mobile number saved for {0} is {1}, which is not a valid 10-digit number. Please correct it in their member profile.", [
						frappe.utils.escape_html(memberName).bold(),
						frappe.utils.escape_html(mobile).bold(),
				  ])
				: __("{0} has no mobile number in their member profile.", [frappe.utils.escape_html(memberName).bold()]),
		});
		return;
	}
	const text = __("Hi {0},", [memberName]) + "\\n\\n" + frappe.msa_one_to_one.whatsapp_text;
	window.open("https://wa.me/" + phone + "?text=" + encodeURIComponent(text), "_blank");
};

// Report scripts share the global scope, so keep this report's names inside a function
(() => {
	const report_name = %s;
	const button_style = "height: 24px; line-height: 22px; padding: 0 8px; margin-top: -1px; vertical-align: top;";
	// Drawn in the button's own text colour
	const mail_icon = frappe.utils.icon(
		"mail", "xs", "", "--icon-stroke: currentColor; stroke: currentColor; margin-right: 4px;"
	);
	// The WhatsApp button is icon-only so both buttons fit the column
	const whatsapp_icon = `<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true"
		style="vertical-align: -2px;"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>`;

	// WhatsApp wants the number with country code and no symbols; members are in India
	const whatsapp_number = (mobile) => {
		let digits = String(mobile || "").replace(/\\D/g, "").replace(/^0+/, "");
		if (digits.length === 10) digits = "91" + digits;
		return digits.length >= 11 ? digits : "";
	};

	// Taller rows for this report only. Frappe's stylesheet fixes the row height (cell height + 2px),
	// so the row and the cell padding have to follow the cellHeight set below; the header
	// row loses its grey background, which otherwise runs on past the last column.
	const style_id = "msa-one-to-one-" + frappe.scrub(report_name);
	if (!document.getElementById(style_id)) {
		const table = `body[data-route="query-report/${report_name}"] .datatable`;
		$(`<style id="${style_id}">
			${table} .dt-row { height: 46px; }
			${table} .dt-cell__content { padding-top: 11px; padding-bottom: 11px; }
			${table} .dt-header .dt-row-header { background-color: transparent; }
		</style>`).appendTo("head");
	}

	frappe.query_reports[report_name] = {
		onload() {
			frappe.msa_load_one_to_one();
		},
		get_datatable_options(options) {
			return Object.assign(options, { inlineFilters: false, cellHeight: 44 });
		},
		formatter(value, row, column, data, default_formatter) {
			if (column.fieldname !== "actions" || !data || !data.member) {
				return default_formatter(value, row, column, data);
			}

			const member_name = frappe.utils.escape_html(data.member_name || "");
			let buttons = `<button class="btn btn-xs btn-primary" style="${button_style}"
				data-member="${frappe.utils.escape_html(data.member)}" data-member-name="${member_name}"
				onclick="frappe.msa_request_one_to_one(this); return false;">${mail_icon}${__("Request 1-2-1")}</button>`;

			buttons += ` <button class="btn btn-xs" style="${button_style} background: #25D366; color: #fff;"
				data-phone="${whatsapp_number(data.actions)}" data-member-name="${member_name}"
				data-mobile="${frappe.utils.escape_html(String(data.actions || ""))}"
				title="${__("Send on WhatsApp")}" aria-label="${__("Send on WhatsApp")}"
				onclick="frappe.msa_whatsapp_one_to_one(this); return false;">${whatsapp_icon}</button>`;
			return buttons;
		},
	};
})();
"""


def add_one_to_one_to_reports():
	"""Set up 1-2-1 requests on a site: the Actions column of the Search Gives / Search Asks
	reports, the "My To Do" menu item, the ToDo "Completed" status and the email footer.

	These live only in the database, so run once per site (safe to repeat):
	bench --site <site> execute my_specific_ask.my_specific_ask.doctype.members.members.add_one_to_one_to_reports
	"""
	updated = []
	for name in ("Search Gives", "Search Asks"):
		if not frappe.db.exists("Report", name):
			continue
		report = frappe.get_doc("Report", name)
		# Drop the column as earlier runs wrote it (first as "1-2-1", or last under either name),
		# then add it after the last column
		query = re.sub(r"\n\t'' as \"1-2-1:[^\"]*\",", "", report.query)
		query = re.sub(r",\n\t(?:''|m\.mobile_number) as \"(?:1-2-1|Actions):[^\"]*\"(?=\nfrom)", "", query)
		report.query = query.replace("\nfrom `tab", f",\n\t{ACTIONS_COLUMN}\nfrom `tab", 1)
		report.javascript = ONE_TO_ONE_REPORT_JS % frappe.as_json(name)
		report.save(ignore_permissions=True)
		updated.append(name)

	# "My To Do" in the My Specific Ask menu, so members can reach their 1-2-1 list
	if frappe.db.exists("Workspace Sidebar", "My Specific Ask"):
		sidebar = frappe.get_doc("Workspace Sidebar", "My Specific Ask")
		if not any(item.link_to == "ToDo" for item in sidebar.items):
			sidebar.append("items", {
				"label": "My To Do", "type": "Link", "link_type": "DocType", "link_to": "ToDo", "icon": "check",
			})
			sidebar.save(ignore_permissions=True)
			updated.append("My To Do menu")
		frappe.cache.delete_key("bootinfo")

	# ToDo status gets a "Completed" choice for 1-2-1s that are done
	frappe.make_property_setter({
		"doctype": "ToDo",
		"fieldname": "status",
		"property": "options",
		"value": "Open\nCompleted\nClosed\nCancelled",
		"property_type": "Text",
	})
	frappe.clear_cache(doctype="ToDo")
	updated.append("ToDo status Completed")

	# No "Sent via Frappe" line under outgoing emails
	settings = frappe.get_single("System Settings")
	if not settings.get("disable_standard_email_footer"):
		settings.disable_standard_email_footer = 1
		settings.save(ignore_permissions=True)
		updated.append("Standard email footer off")

	setup_home_page()
	updated.append("Home page")

	frappe.db.commit()
	return updated


HOME_WELCOME = "Welcome to My Specific Ask Desk"
HOME_TEXT = (
	"Please add your details and keep your member details updated. "
	"Update your Asks and Gives regularly to get maximum returns."
)
# label -> Number Card fields. Gives and Asks are child tables, which members cannot be
# given a Document Type card for, so those two count through a method.
HOME_CARDS = {
	"Total Members": {"type": "Document Type", "document_type": "Members", "function": "Count"},
	"Total Gives": {
		"type": "Custom",
		"document_type": "Members",
		"method": "my_specific_ask.my_specific_ask.doctype.members.members.get_total_gives",
	},
	"Total Asks": {
		"type": "Custom",
		"document_type": "Members",
		"method": "my_specific_ask.my_specific_ask.doctype.members.members.get_total_asks",
	},
}
HOME_SHORTCUTS = [
	{"label": "Members", "type": "DocType", "link_to": "Members", "doc_view": "List"},
	{"label": "Search Gives", "type": "Report", "link_to": "Search Gives", "report_ref_doctype": "Members"},
	{"label": "Search Asks", "type": "Report", "link_to": "Search Asks", "report_ref_doctype": "Members"},
	{"label": "My To Do", "type": "DocType", "link_to": "ToDo", "doc_view": "List"},
]


def setup_home_page():
	"""My Specific Ask workspace: welcome text, the three totals and the shortcuts."""
	if not frappe.db.exists("Workspace", "My Specific Ask"):
		return

	cards = []
	for label, fields in HOME_CARDS.items():
		name = frappe.db.get_value("Number Card", {"label": label})
		card = frappe.get_doc("Number Card", name) if name else frappe.new_doc("Number Card")
		card.update({
			"label": label,
			"module": "My Specific Ask",
			"is_public": 1,
			"show_percentage_stats": 0,
			"filters_json": "[]",
			**fields,
		})
		card.save(ignore_permissions=True)
		cards.append({"number_card_name": card.name, "label": label})

	shortcuts = [s for s in HOME_SHORTCUTS if s["type"] != "Report" or frappe.db.exists("Report", s["link_to"])]

	def heading(block_id, text, size):
		return {"id": block_id, "type": "header", "data": {"text": f'<span class="{size}"><b>{text}</b></span>', "col": 12}}

	content = [
		heading("msa_header", HOME_WELCOME, "h3"),
		{"id": "msa_welcome", "type": "paragraph", "data": {"text": HOME_TEXT, "col": 12}},
		heading("msa_totals", "Overview", "h5"),
		*[
			{"id": "msa_card_" + frappe.scrub(c["label"]), "type": "number_card", "data": {"number_card_name": c["label"], "col": 4}}
			for c in cards
		],
		{"id": "msa_spacer", "type": "spacer", "data": {"col": 12}},
		heading("msa_shortcuts", "Shortcuts", "h5"),
		*[
			{"id": "msa_" + frappe.scrub(s["label"]), "type": "shortcut", "data": {"shortcut_name": s["label"], "col": 3}}
			for s in shortcuts
		],
	]

	workspace = frappe.get_doc("Workspace", "My Specific Ask")
	workspace.set("number_cards", cards)
	workspace.set("shortcuts", shortcuts)
	workspace.content = frappe.as_json(content)
	workspace.save(ignore_permissions=True)


def set_outgoing_email(email, password):
	"""Send all of the site's mail from `email`, a Gmail / Google Workspace address, using its app password.

	The password is given on the command line so it is never kept in the code. Saving the
	account logs in to Gmail, so a wrong address or password fails here instead of later:
	bench --site <site> execute my_specific_ask.my_specific_ask.doctype.members.members.set_outgoing_email
		--kwargs "{'email': '<address>', 'password': '<app password>'}"
	"""
	name = frappe.db.get_value("Email Account", {"email_id": email})
	if name:
		account = frappe.get_doc("Email Account", name)
	else:
		account = frappe.new_doc("Email Account")
		# The account's name is what recipients see as the sender
		account.email_account_name = email if frappe.db.exists("Email Account", APP_TITLE) else APP_TITLE

	account.update({
		"email_id": email,
		"auth_method": "Basic",
		"password": password.replace(" ", ""),
		"awaiting_password": 0,
		"enable_outgoing": 1,
		"default_outgoing": 1,
		"smtp_server": "smtp.gmail.com",
		"smtp_port": "587",
		"use_tls": 1,
	})
	account.save(ignore_permissions=True)
	frappe.db.commit()
	return f"Outgoing mail now goes from {email} (Email Account: {account.name})"


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
		if not is_admin(user.name):
			user.add_roles(MEMBER_ROLE)

		frappe.db.set_value("Members", m.name, "user", email)
		linked += 1

	frappe.db.commit()
	return {"created": created, "linked": linked, "skipped": skipped}
