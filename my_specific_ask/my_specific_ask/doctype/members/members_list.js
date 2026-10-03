// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

// Members list: "Search Asks" / "Search Gives" boxes. A member stays in the list when any
// row of that table contains the text in any of its columns; both boxes must match if both are filled.
frappe.listview_settings["Members"] = {
	add_fields: ["user", "full_name", "gives_count", "asks_count", "power_team"],

	// "Gives / Asks" column (added in onload): "G-5, A-3" - how many Gives and Asks the member has listed
	formatters: {
		gives_count(value, df, doc) {
			const tip = __("{0} Gives, {1} Asks", [doc.gives_count || 0, doc.asks_count || 0]);
			return `<span class="ellipsis" title="${tip}">G-${doc.gives_count || 0}, A-${doc.asks_count || 0}</span>`;
		},
	},

	// "Request 1-2-1" on every row but your own: emails that member and adds a ToDo for you
	button: {
		show(doc) {
			return doc.user !== frappe.session.user;
		},
		get_label() {
			const mail_icon = frappe.utils.icon("mail", "xs", "", "margin-right: 4px;");
			return mail_icon + __("Request 1-2-1");
		},
		get_description(doc) {
			return __("Email {0} a 1-2-1 request and add it to your ToDo list", [frappe.utils.escape_html(doc.full_name)]);
		},
		action(doc) {
			frappe.confirm(__("Send a 1-2-1 request to {0}?", [frappe.utils.escape_html(doc.full_name).bold()]), () => {
				frappe.call({
					method: "my_specific_ask.my_specific_ask.doctype.members.members.request_one_to_one",
					args: { member: doc.name },
					freeze: true,
					freeze_message: __("Sending request..."),
					callback: () =>
						frappe.show_alert({
							message: __("1-2-1 request emailed and added to your <a href='/desk/todo'>ToDo list</a>."),
							indicator: "green",
						}),
				});
			});
		},
	},

	onload(listview) {
		// Columns start: Full Name, Gives / Asks, Network, Power Team. "Gives / Asks" is not a
		// field of its own, so they are put in place each time the list works out its columns
		// (also after List Settings change).
		const setup_columns = listview.setup_columns.bind(listview);
		listview.setup_columns = () => {
			setup_columns();
			const columns = listview.columns;
			// The column of a field: taken out of where it is, or made when it is not shown
			const take = (fieldname) => {
				const at = columns.findIndex((col) => col.df && col.df.fieldname === fieldname);
				return at === -1
					? { type: "Field", df: frappe.meta.get_docfield("Members", fieldname) }
					: columns.splice(at, 1)[0];
			};
			// Position 1 is the hidden tag column
			columns.splice(
				2,
				0,
				{ type: "Field", df: { label: __("Gives / Asks"), fieldname: "gives_count", fieldtype: "Data" } },
				take("network"),
				take("power_team")
			);
		};
		// The header was drawn before onload
		listview.setup_columns();
		listview.render_header(true);

		// Badge after the name for the Gives a member has listed; highest level first.
		// Fewer than 6 Gives: no badge.
		const badges = [
			{ min: 25, label: __("Platinum"), rim: "#d3e3ee", face: "#5f86a3" },
			{ min: 19, label: __("Gold"), rim: "#ffd98a", face: "#f59e0b" },
			{ min: 13, label: __("Silver"), rim: "#e1e4e8", face: "#8d96a3" },
			{ min: 6, label: __("Bronze"), rim: "#e6bd95", face: "#b4682a" },
		];
		// Rosette with a tick: ribbons, a scalloped rim (8 small circles round a big one), the face
		const rim_circles = [0, 1, 2, 3, 4, 5, 6, 7]
			.map((i) => {
				const angle = (i * Math.PI) / 4;
				return `<circle cx="${(12 + 6.6 * Math.cos(angle)).toFixed(2)}" cy="${(9.5 + 6.6 * Math.sin(angle)).toFixed(2)}" r="2.4"/>`;
			})
			.join("");
		const badge_html = (gives) => {
			const badge = badges.find((b) => gives >= b.min);
			if (!badge) return "";
			// Shown when the mouse is over the badge
			const tip = __("{0} badge - {1} Gives", [badge.label, gives]);
			return `<span class="msa-gives-badge" title="${tip}" style="display: inline-flex; flex-shrink: 0; margin-left: 10px; vertical-align: middle;">
				<svg viewBox="0 0 24 24" width="20" height="20" role="img" aria-label="${tip}">
					<path d="M8.2 13 5 22.5l3.4-1.2 1.9 2.7 2.4-8z" fill="#ff4d4f"/>
					<path d="M15.8 13 19 22.5l-3.4-1.2-1.9 2.7-2.4-8z" fill="#e8383b"/>
					<g fill="${badge.rim}"><circle cx="12" cy="9.5" r="7"/>${rim_circles}</g>
					<circle cx="12" cy="9.5" r="5" fill="${badge.face}"/>
					<path d="M9.5 9.6l1.8 1.8 3.3-3.5" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
				</svg>
			</span>`;
		};

		// The name column's formatter can only return text, so the badge goes into the
		// element the list builds for that column, just after the name.
		const get_subject_element = listview.get_subject_element.bind(listview);
		listview.get_subject_element = (doc, title) => {
			const element = get_subject_element(doc, title);
			const link = element.querySelector("a");
			if (link) link.insertAdjacentHTML("afterend",badge_html(doc.gives_count || 0));
			return element;
		};

		// The list sizes the name column from the name's text alone, which cuts the badge off:
		// widen it by the badge and a gap before the next column.
		const apply_column_widths = listview.apply_column_widths.bind(listview);
		listview.apply_column_widths = () => {
			apply_column_widths();
			if (listview.list_view_settings?.disable_scrolling || !listview.column_max_widths.full_name) return;
			const width = listview.column_max_widths.full_name + 50;
			listview.$result
				.find('.level-left .list-row-col[data-fieldname="full_name"]')
				.css({ width: width, flex: `1 0 ${width}px` });
		};

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
