# Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

from collections import Counter

import frappe


@frappe.whitelist()
def get_power_teams():
	"""Every Power Team with the number of members in it, biggest team first.

	Members can pick a Power Team but not browse the list, so the teams are read here
	for anyone who may see Members."""
	frappe.has_permission("Members", throw=True)

	members = Counter(frappe.get_all("Members", filters={"power_team": ["is", "set"]}, pluck="power_team"))
	teams = frappe.get_all(
		"Power Team", fields=["name", "power_team_name", "description"], order_by="power_team_name"
	)
	for team in teams:
		team.members = members.get(team.name, 0)
	# Stable sort: teams of the same size stay in name order
	return sorted(teams, key=lambda team: -team.members)
