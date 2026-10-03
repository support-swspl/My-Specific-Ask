// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

// Asks Dashboard and Gives Dashboard pages (page/asks_dashboard, page/gives_dashboard).
// Two pie charts - by industry and by classification - of all members' Asks or Gives, each with
// its list underneath. Clicking a line opens, in a new browser tab, the Members list of the
// members who have such an Ask / Give.
//
// options: title of the page, table ("Members Ask" or "Members Give"), rows_label ("Asks" or "Gives")
frappe.msa_ask_give_dashboard = function (wrapper, options) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: options.title,
		single_column: true,
	});

	const esc = frappe.utils.escape_html;
	const sections = [
		{ field: "industry", label: __("Industry") },
		{ field: "classification", label: __("Classification") },
	];

	const $body = $(`<div class="row" style="padding-top: var(--padding-md);"></div>`).appendTo(page.main);
	for (const section of sections) {
		section.$card = $(`
			<div class="col-md-6" style="margin-bottom: var(--margin-lg);">
				<div class="frappe-card" style="padding: var(--padding-md);">
					<div class="h6">${__("{0} by {1}", [options.rows_label, section.label])}</div>
					<div class="msa-chart"></div>
					<div class="text-muted small" style="margin: var(--margin-md) 0 var(--margin-sm);">
						${__("Click a line to open its members in a new tab.")}
					</div>
					<div class="msa-list"></div>
				</div>
			</div>
		`).appendTo($body);

		// The Members list filtered on this column of the Asks / Gives table, in a new browser tab
		section.$card.on("click", "tr[data-value]", function () {
			const url = frappe.router.make_url([frappe.router.slug("Members")]);
			const filter = encodeURIComponent(`${options.table}.${section.field}`);
			window.open(`${url}?${filter}=${encodeURIComponent(this.dataset.value)}`, "_blank");
		});
	}

	const render = (section, groups) => {
		const $chart = section.$card.find(".msa-chart");
		const $list = section.$card.find(".msa-list");
		if (!groups.length) {
			$chart.html(`<div class="text-muted text-center" style="padding: var(--padding-xl);">
				${__("No {0} have been added yet.", [options.rows_label])}</div>`);
			$list.empty();
			return;
		}

		$chart.empty();
		new frappe.Chart($chart[0], {
			type: "pie",
			height: 280,
			// The biggest slices; the chart puts the rest together in one slice
			maxSlices: 10,
			data: {
				labels: groups.map((group) => group.value),
				datasets: [{ values: groups.map((group) => group.rows) }],
			},
		});

		const rows = groups
			.map(
				(group) => `
				<tr data-value="${esc(group.value)}" style="cursor: pointer;">
					<td><b>${esc(group.value)}</b></td>
					<td class="text-right">${group.rows}</td>
					<td class="text-right">${group.members}</td>
				</tr>`
			)
			.join("");
		$list.html(`
			<div style="overflow-x: auto;">
				<table class="table table-hover" style="margin-bottom: 0;">
					<thead>
						<tr>
							<th>${section.label}</th>
							<th class="text-right">${options.rows_label}</th>
							<th class="text-right">${__("Members")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		`);
	};

	// Also called every time the page is shown, so the numbers are current after a profile was edited
	wrapper.msa_refresh = async () => {
		const r = await frappe.call(
			"my_specific_ask.my_specific_ask.doctype.members.members.get_ask_give_breakdown",
			{ table: options.table }
		);
		for (const section of sections) render(section, (r.message || {})[section.field] || []);
	};
	page.set_secondary_action(__("Refresh"), () => wrapper.msa_refresh(), "refresh");
	wrapper.msa_refresh();
};
