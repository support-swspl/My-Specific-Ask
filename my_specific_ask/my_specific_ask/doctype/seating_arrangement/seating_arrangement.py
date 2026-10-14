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
