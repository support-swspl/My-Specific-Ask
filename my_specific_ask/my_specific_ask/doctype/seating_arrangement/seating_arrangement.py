# Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

from itertools import zip_longest

import frappe
from frappe import _
from frappe.model.document import Document

MIXED_TEAM = "Mixed Power Team"


class SeatingArrangement(Document):
	"""Seats the Active members at tables of `members_per_team`. Only this document is written:
	the Power Teams and the members' own Power Team stay as they are."""

	def validate(self):
		if not self.title:
			self.title = _("Seating {0}").format(frappe.utils.formatdate(self.meeting_date or frappe.utils.today()))
		if (self.members_per_team or 0) < 2:
			frappe.throw(_("Members per Power Team must be at least 2."))

		self.total_members = len(self.seats)
		self.total_teams = len({seat.seating_team for seat in self.seats})

	@frappe.whitelist()
	def generate_seating(self):
		"""Replaces the seats with a fresh arrangement of the current Active members."""
		self.check_permission("write")
		if (self.members_per_team or 0) < 2:
			frappe.throw(_("Members per Power Team must be at least 2."))

		self.set("seats", [])
		for team, team_type, members in arrange(get_active_members(), self.members_per_team):
			for member in members:
				self.append("seats", {
					"seating_team": team,
					"team_type": team_type,
					"member": member.name,
					"member_name": member.full_name,
					"company_name": member.company_name,
					"power_team": member.power_team,
					"power_team_name": member.power_team_name,
				})
		self.save()

	@frappe.whitelist()
	def email_schedules(self):
		"""Email each seated member their own 1-2-1 PDF, in the background. Returns how many get one."""
		self.check_permission("write")
		if not self.seats:
			frappe.throw(_("Generate the seating first."))
		with_email = frappe.get_all(
			"Members", filters={"name": ["in", [s.member for s in self.seats]], "email": ["is", "set"]}, pluck="name"
		)
		frappe.enqueue(
			"my_specific_ask.my_specific_ask.doctype.seating_arrangement.seating_arrangement.email_member_schedules",
			queue="long",
			timeout=1800,
			seating_arrangement=self.name,
			enqueue_after_commit=True,
		)
		return {"emailed": len(with_email), "without_email": len(self.seats) - len(with_email)}


def get_active_members():
	members = frappe.get_all(
		"Members",
		# A member with no status set counts as Active
		filters={"status": ["not in", ["Ex Member", "Break", "Visitor"]]},
		fields=["name", "full_name", "company_name", "power_team"],
		order_by="full_name asc",
	)
	team_names = dict(frappe.get_all("Power Team", fields=["name", "power_team_name"], as_list=True))
	for member in members:
		member.power_team_name = team_names.get(member.power_team) if member.power_team else None
	return members


def arrange(members, size):
	"""[(team name, type, members)]: each Power Team fills as many full tables of `size` as it can,
	keeping its own name ("Sales", "Sales 2", ...). What is left of every team, and members without
	a Power Team, are seated in Mixed Power Team 1, 2, ... of `size`, taking one member from each
	team in turn so a mixed table holds people from different teams."""
	by_team = {}
	for member in members:
		by_team.setdefault(member.power_team or None, []).append(member)

	def team_title(team):
		return by_team[team][0].power_team_name or team

	tables, leftovers = [], []
	for team in sorted((t for t in by_team if t), key=lambda t: team_title(t).lower()):
		team_members = by_team[team]
		full = len(team_members) // size
		for i in range(full):
			name = team_title(team) if i == 0 else f"{team_title(team)} {i + 1}"
			tables.append((name, "Power Team", team_members[i * size:(i + 1) * size]))
		leftovers.append(team_members[full * size:])
	leftovers.append(by_team.get(None, []))

	mixed = [m for group in zip_longest(*leftovers) for m in group if m is not None]
	for i in range(0, len(mixed), size):
		tables.append((f"{MIXED_TEAM} {i // size + 1}", "Mixed", mixed[i:i + size]))
	return tables


def one_to_one_rounds(people):
	"""Round-robin 1-2-1s for one table: [(pairs, sitting out)], one entry per round. Every two
	people meet exactly once; with an odd number one person sits out each round."""
	people = list(people)
	if len(people) < 2:
		return []
	if len(people) % 2:
		people.append(None)
	rounds = []
	for _round in range(len(people) - 1):
		half = len(people) // 2
		pairs = list(zip(people[:half], reversed(people[half:])))
		rounds.append((
			[(a, b) for a, b in pairs if a is not None and b is not None],
			next((b if a is None else a for a, b in pairs if a is None or b is None), None),
		))
		# Circle method: the first person stays, everyone else moves one place
		people = [people[0], people[-1], *people[1:-1]]
	return rounds


def get_conclave_tables(doc):
	"""Each table with its members and its 1-2-1 rounds; the rounds pair the members themselves.
	Used by the Conclave 1-2-1 Schedule print format and each member's own 1-2-1 PDF."""
	details = {
		m.name: m
		for m in frappe.get_all(
			"Members",
			filters={"name": ["in", [s.member for s in doc.seats] or [""]]},
			fields=["name", "category", "mobile_number", "email"],
		)
	}
	tables = {}
	for seat in doc.seats:
		table = tables.setdefault(seat.seating_team, {"name": seat.seating_team, "type": seat.team_type, "members": []})
		member = details.get(seat.member) or frappe._dict()
		table["members"].append(frappe._dict(
			id=seat.member,
			name=seat.member_name or seat.member,
			company=seat.company_name,
			category=member.category,
			mobile=member.mobile_number,
			email=member.email,
			power_team=seat.power_team_name or seat.power_team,
		))
	for number, table in enumerate(tables.values(), start=1):
		table["number"] = number
		table["rounds"] = one_to_one_rounds(table["members"])
	return list(tables.values())


def get_member_schedule(doc, member, tables=None):
	"""`member`'s table and, round by round, who they do their 1-2-1 with (None: sitting out)."""
	for table in tables or get_conclave_tables(doc):
		me = next((m for m in table["members"] if m.id == member), None)
		if not me:
			continue
		rounds = []
		for pairs, _out in table["rounds"]:
			rounds.append(next((b if a is me else a for a, b in pairs if me in (a, b)), None))
		return frappe._dict(me=me, table=table, rounds=rounds)


MEMBER_SCHEDULE_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
	body { font-family: Helvetica, Arial, sans-serif; font-size: 12px; color: #171717; }
	h1 { font-size: 20px; margin: 0 0 2px; }
	.muted { color: #6b7280; }
	table { width: 100%; border-collapse: collapse; margin: 10px 0 16px; }
	th, td { border: 1px solid #d1d5db; padding: 6px 8px; text-align: left; vertical-align: top; }
	th { background: #f3f4f6; }
	.num { width: 48px; text-align: center; }
	.out { color: #6b7280; font-style: italic; }
</style></head><body>
	<h1>{{ _("Your 1-2-1 Schedule") }}</h1>
	<div class="muted">{{ doc.title }}{% if doc.meeting_date %} &middot; {{ frappe.format(doc.meeting_date, {"fieldtype": "Date"}) }}{% endif %}</div>

	<p style="font-size: 14px; margin-top: 14px;">
		<b>{{ s.me.name }}</b>{% if s.me.company %}, {{ s.me.company }}{% endif %}<br>
		{{ _("You sit at Table {0}: {1}").format(s.table.number, s.table.name) }}
	</p>

	{% if s.rounds %}
	<table>
		<tr><th class="num">{{ _("Round") }}</th><th>{{ _("Your 1-2-1 With") }}</th><th>{{ _("Company") }}</th><th>{{ _("Category") }}</th><th>{{ _("Mobile") }}</th></tr>
		{% for p in s.rounds %}
		<tr>
			<td class="num">{{ loop.index }}</td>
			{% if p %}
			<td><b>{{ p.name }}</b></td><td>{{ p.company or "" }}</td><td>{{ p.category or "" }}</td><td>{{ p.mobile or "" }}</td>
			{% else %}
			<td colspan="4" class="out">{{ _("Sitting out this round") }}</td>
			{% endif %}
		</tr>
		{% endfor %}
	</table>
	{% else %}
	<p class="muted">{{ _("You are the only member at your table, so there are no 1-2-1 rounds.") }}</p>
	{% endif %}
	<p class="muted">{{ _("Do a 1-2-1 with each member above, in this order. Powered by My Specific Ask.") }}</p>
</body></html>"""

MEMBER_SCHEDULE_EMAIL = """<p>{{ _("Dear {0},").format(s.me.name) }}</p>
<p>{{ _("Your 1-2-1 schedule for {0} is attached. You sit at Table {1}: {2}.").format(doc.title, s.table.number, s.table.name) }}</p>
<p>{{ _("Your 1-2-1s, round by round:") }}</p>
<ol>{% for p in s.rounds %}<li>{% if p %}<b>{{ p.name }}</b>{% if p.company %}, {{ p.company }}{% endif %}{% else %}<i>{{ _("Sitting out") }}</i>{% endif %}</li>{% endfor %}</ol>
<p>{{ _("Regards,") }}<br>My Specific Ask</p>"""


def member_schedule_pdf(doc, schedule):
	"""(file name, PDF bytes) of one member's own 1-2-1 schedule, from get_member_schedule."""
	from frappe.utils.pdf import get_pdf

	html = frappe.render_template(MEMBER_SCHEDULE_HTML, {"doc": doc, "s": schedule})
	return _("1-2-1 Schedule - {0}.pdf").format(schedule.me.name), get_pdf(html)


def latest_seating_for(member):
	"""Name of the most recently generated Seating Arrangement that seats `member`."""
	parents = frappe.get_all(
		"Seating Arrangement Seat", filters={"member": member, "parenttype": "Seating Arrangement"}, pluck="parent"
	)
	if not parents:
		return None
	return frappe.get_all(
		"Seating Arrangement", filters={"name": ["in", parents]}, order_by="modified desc", limit=1, pluck="name"
	)[0]


def my_member_profile():
	return frappe.db.get_value("Members", {"user": frappe.session.user}, "name")


@frappe.whitelist()
def get_my_schedule():
	"""Home page: the newest Seating Arrangement the logged-in member is seated in, if any."""
	member = my_member_profile()
	seating = member and latest_seating_for(member)
	if seating:
		return frappe.db.get_value("Seating Arrangement", seating, ["name", "title", "meeting_date"], as_dict=True)


@frappe.whitelist()
def download_my_schedule(seating_arrangement: str | None = None, member: str | None = None):
	"""The logged-in member's own 1-2-1 PDF from their newest seating. An administrator may ask
	for any member's PDF from any seating."""
	from my_specific_ask.my_specific_ask.doctype.members.members import is_admin

	if not is_admin():
		member, seating_arrangement = my_member_profile(), None
	if not member:
		frappe.throw(_("This login has no member profile."))
	seating_arrangement = seating_arrangement or latest_seating_for(member)
	doc = seating_arrangement and frappe.get_doc("Seating Arrangement", seating_arrangement)
	schedule = doc and get_member_schedule(doc, member)
	if not schedule:
		frappe.throw(_("You have not been given a seat in a Seating Arrangement yet."))

	frappe.local.response.filename, frappe.local.response.filecontent = member_schedule_pdf(doc, schedule)
	frappe.local.response.type = "pdf"


def email_member_schedules(seating_arrangement):
	"""Background job: email every seated member with an email address their own 1-2-1 PDF."""
	from email.utils import formataddr

	from frappe.email.doctype.email_account.email_account import EmailAccount

	from my_specific_ask.my_specific_ask.doctype.members.members import APP_TITLE

	doc = frappe.get_doc("Seating Arrangement", seating_arrangement)
	account = EmailAccount.find_default_outgoing()
	sender = formataddr((APP_TITLE, account.email_id)) if account and account.email_id else None

	tables = get_conclave_tables(doc)
	for table in tables:
		for member in table["members"]:
			if not member.email:
				continue
			schedule = get_member_schedule(doc, member.id, tables)
			fname, pdf = member_schedule_pdf(doc, schedule)
			frappe.sendmail(
				recipients=member.email,
				sender=sender,
				subject=_("Your 1-2-1 Schedule: {0}").format(doc.title),
				message=frappe.render_template(MEMBER_SCHEDULE_EMAIL, {"doc": doc, "s": schedule}),
				attachments=[{"fname": fname, "fcontent": pdf}],
				reference_doctype=doc.doctype,
				reference_name=doc.name,
				with_container=True,
			)
	frappe.db.set_value(doc.doctype, doc.name, "schedules_emailed_on", frappe.utils.now_datetime(), update_modified=False)
