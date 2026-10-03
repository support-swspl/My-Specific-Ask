// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

// Power Team Dashboard: a pie chart of members per Power Team and the list of teams under it.
// Clicking a team opens the Members list for that team in a new browser tab.
frappe.pages["power-team-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Power Team Dashboard"),
		single_column: true,
	});

	const esc = frappe.utils.escape_html;
	const $body = $(`
		<div class="msa-power-teams" style="padding: var(--padding-md) 0;">
			<div class="frappe-card" style="padding: var(--padding-md); margin-bottom: var(--margin-lg);">
				<div class="h6">${__("Members by Power Team")}</div>
				<div class="msa-pt-chart"></div>
			</div>
			<div class="frappe-card" style="padding: var(--padding-md); margin-bottom: var(--margin-lg);">
				<div class="h6">${__("Power Teams")}</div>
				<div class="text-muted small" style="margin-bottom: var(--margin-sm);">
					${__("Click a Power Team to open its members in a new tab.")}
				</div>
				<div class="msa-pt-teams"></div>
			</div>
		</div>
	`).appendTo(page.main);

	const $chart = $body.find(".msa-pt-chart");
	const $teams = $body.find(".msa-pt-teams");
	let teams = [];

	const render_chart = () => {
		const with_members = teams.filter((team) => team.members > 0);
		if (!with_members.length) {
			$chart.html(`<div class="text-muted text-center" style="padding: var(--padding-xl);">
				${__("No member belongs to a Power Team yet.")}</div>`);
			return;
		}
		$chart.empty();
		new frappe.Chart($chart[0], {
			type: "pie",
			height: 300,
			data: {
				labels: with_members.map((team) => team.power_team_name),
				datasets: [{ values: with_members.map((team) => team.members) }],
			},
		});
	};

	const render_teams = () => {
		if (!teams.length) {
			$teams.html(`<div class="text-muted">${__("No Power Teams have been added yet.")}</div>`);
			return;
		}
		const rows = teams
			.map(
				(team) => `
				<tr data-team="${esc(team.name)}" style="cursor: pointer;">
					<td style="white-space: nowrap;"><b>${esc(team.power_team_name)}</b></td>
					<td class="text-right" style="white-space: nowrap; padding-left: var(--padding-xl);"><b>${team.members}</b></td>
				</tr>`
			)
			.join("");
		// Only as wide as its two columns, so the count sits beside the team name
		$teams.html(`
			<div style="overflow-x: auto;">
				<table class="table table-hover" style="width: auto; margin-bottom: 0;">
					<thead>
						<tr>
							<th>${__("Power Team")}</th>
							<th class="text-right" style="padding-left: var(--padding-xl);">${__("Members")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		`);
	};

	// The Members list of that team, in a new browser tab; a member opens from there as usual
	$teams.on("click", "tr[data-team]", function () {
		const url = frappe.router.make_url([frappe.router.slug("Members")]);
		window.open(url + "?power_team=" + encodeURIComponent(this.dataset.team), "_blank");
	});

	// Called every time the page is shown, so the numbers are current after a profile was edited
	wrapper.msa_refresh = async () => {
		const r = await frappe.call(
			"my_specific_ask.my_specific_ask.page.power_team_dashboard.power_team_dashboard.get_power_teams"
		);
		teams = r.message || [];
		render_chart();
		render_teams();
	};
	page.set_secondary_action(__("Refresh"), () => wrapper.msa_refresh(), "refresh");
};

frappe.pages["power-team-dashboard"].on_page_show = function (wrapper) {
	wrapper.msa_refresh && wrapper.msa_refresh();
};
