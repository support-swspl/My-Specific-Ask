// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

// Members list: "Search Asks" / "Search Gives" boxes. A member stays in the list when any
// row of that table contains the text in any of its columns; both boxes must match if both are filled.
frappe.listview_settings["Members"] = {
	onload(listview) {
		const tables = {
			ask: {
				label: __("Search Asks"),
				doctype: "Members Ask",
				fields: ["company_name", "full_name", "department", "industry", "classification", "city", "ma_country", "required_for"],
			},
			give: {
				label: __("Search Gives"),
				doctype: "Members Give",
				fields: [
					"company_name", "designation", "department", "industry", "classification", "city",
					"mg_country", "multi_location", "known_since", "interaction_frequency", "nature_of_relationship",
				],
			},
		};
		const search_text = { ask: "", give: "" };

		const members_matching = async (table, text) => {
			const rows = await frappe.db.get_list("Members", {
				fields: ["name"],
				limit: 0,
				or_filters: table.fields.map((field) => [table.doctype, field, "like", `%${text}%`]),
			});
			return rows.map((row) => row.name);
		};

		const apply = async () => {
			let names = null;
			for (const [key, table] of Object.entries(tables)) {
				const text = search_text[key].trim();
				if (!text) continue;
				const found = await members_matching(table, text);
				names = names === null ? found : names.filter((name) => found.includes(name));
			}

			await listview.filter_area.remove("name");
			if (names !== null) {
				// "in" with an empty list would match everything, so use a name that cannot exist
				await listview.filter_area.add([["Members", "name", "in", names.length ? names : ["-no match-"]]]);
			}
		};

		// Plain inputs in their own row: fields added with page.add_field become list filters,
		// and the list would then query them as Members columns.
		const $row = $(`<div class="msa-list-search flex" style="gap: var(--margin-sm); padding: var(--padding-sm) var(--padding-md);"></div>`)
			.prependTo(listview.$frappe_list);
		for (const [key, table] of Object.entries(tables)) {
			const $input = $(`<input type="search" class="form-control" style="max-width: 280px;">`)
				.attr("placeholder", table.label)
				.appendTo($row);
			$input.on(
				"input",
				frappe.utils.debounce(() => {
					search_text[key] = $input.val() || "";
					apply();
				}, 400)
			);
		}
	},
};
