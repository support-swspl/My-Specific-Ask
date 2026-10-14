# Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import UnitTestCase

from my_specific_ask.my_specific_ask.doctype.seating_arrangement.seating_arrangement import arrange


def members(team, count):
	return [
		frappe._dict(name=f"{team}-{i}", power_team=team, power_team_name=team and f"Team {team}")
		for i in range(count)
	]


class UnitTestSeatingArrangement(UnitTestCase):
	def test_leftovers_go_to_mixed_team(self):
		tables = arrange(members("A", 8), 6)
		self.assertEqual([(t[0], len(t[2])) for t in tables], [("Team A", 6), ("Mixed Power Team 1", 2)])

	def test_large_team_keeps_several_tables(self):
		tables = arrange(members("A", 13), 6)
		self.assertEqual([(t[0], len(t[2])) for t in tables], [("Team A", 6), ("Team A 2", 6), ("Mixed Power Team 1", 1)])

	def test_mixed_teams_take_one_from_each_team_in_turn(self):
		tables = arrange(members("A", 9) + members("B", 10) + members(None, 2), 6)
		mixed = [t for t in tables if t[1] == "Mixed"]
		self.assertEqual([t[0] for t in mixed], ["Mixed Power Team 1", "Mixed Power Team 2"])
		self.assertEqual([m.power_team for m in mixed[0][2]], ["A", "B", None, "A", "B", None])
		self.assertEqual(len(mixed[1][2]), 3)

	def test_every_member_is_seated_once(self):
		everyone = members("A", 7) + members("B", 3) + members(None, 4)
		seated = [m.name for t in arrange(everyone, 4) for m in t[2]]
		self.assertCountEqual(seated, [m.name for m in everyone])
