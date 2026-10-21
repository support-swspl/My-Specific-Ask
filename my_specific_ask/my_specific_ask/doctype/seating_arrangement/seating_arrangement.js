// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Seating Arrangement", {
	refresh(frm) {
		render_seating(frm);
		frm.add_custom_button(__("Generate Seating"), () => ask_team_size(frm)).addClass("btn-primary");
		if (!frm.is_new() && (frm.doc.seats || []).length) {
			frm.add_custom_button(__("Conclave 1-2-1 PDF"), () => open_conclave_pdf(frm));
			if (frm.doc.email_members) {
				frm.add_custom_button(__("Email 1-2-1 PDFs to Members"), () => email_schedules(frm));
			}
		}
		// A new arrangement opens straight on the question, so OK is all it takes
		if (frm.is_new() && !frm._asked_team_size) {
			frm._asked_team_size = true;
			ask_team_size(frm);
		}
	},
	email_members(frm) {
		// Show or hide the Email button with the tick
		frm.refresh();
	},
});

function ask_team_size(frm) {
	const replacing = (frm.doc.seats || []).length > 0;
	frappe.prompt(
		[{
			fieldname: "members_per_team",
			fieldtype: "Int",
			label: __("Members per Power Team"),
			default: frm.doc.members_per_team || 6,
			reqd: 1,
			description:
				__("Example: with 6, a Power Team of 8 sits 6 together and its other 2 go to Mixed Power Team 1.") +
				(replacing ? "<br><b>" + __("This replaces the current seating.") + "</b>" : ""),
		},
		{
			fieldname: "email_members",
			fieldtype: "Check",
			label: __("Email Members their 1-2-1 PDF"),
			default: frm.doc.email_members || 0,
			description: __("Ticked: after the seating is made, each member is emailed who they do a 1-2-1 with. Not ticked: no emails."),
		}],
		(values) => {
			if (values.members_per_team < 2) {
				frappe.msgprint(__("Members per Power Team must be at least 2."));
				return;
			}
			frm.set_value({ members_per_team: values.members_per_team, email_members: values.email_members ? 1 : 0 })
				.then(() => (frm.is_dirty() || frm.is_new() ? frm.save() : null))
				.then(() => frm.call({ method: "generate_seating", doc: frm.doc, freeze: true, freeze_message: __("Arranging seats...") }))
				.then(() => {
					frm.refresh();
					if (frm.doc.email_members) {
						send_schedules(frm);
						return;
					}
					const tables = new Set((frm.doc.seats || []).map((seat) => seat.seating_team)).size;
					frappe.confirm(
						__("{0} members seated at {1} tables. Download the Conclave 1-2-1 PDF now?", [(frm.doc.seats || []).length, tables]),
						() => open_conclave_pdf(frm)
					);
				});
		},
		__("Seating Arrangement"),
		__("OK")
	);
}

function open_conclave_pdf(frm) {
	const params = new URLSearchParams({
		doctype: frm.doctype,
		name: frm.doc.name,
		format: "Conclave 1-2-1 Schedule",
		no_letterhead: 1,
	});
	window.open(`/api/method/frappe.utils.print_format.download_pdf?${params}`);
}

function email_schedules(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Please save first."));
		return;
	}
	const already = frm.doc.schedules_emailed_on
		? "<br><br>" + __("They were already emailed on {0}.", [frappe.datetime.str_to_user(frm.doc.schedules_emailed_on)])
		: "";
	frappe.confirm(
		__("Email each of the {0} seated members their own 1-2-1 PDF: who they do a 1-2-1 with, round by round?", [
			frm.doc.seats.length,
		]) + already,
		() => send_schedules(frm)
	);
}

function send_schedules(frm) {
	frm.call({ method: "email_schedules", doc: frm.doc, freeze: true }).then((r) => {
		const { emailed, without_email } = r.message;
		frappe.msgprint(
			__("Sending their 1-2-1 PDF to {0} members in the background.", [emailed]) +
				(without_email ? "<br>" + __("{0} members have no email address and were skipped.", [without_email]) : "")
		);
	});
}

// The tables in seating order, numbered as in the Conclave PDF. "Sales 2" reads like another team,
// so each table shows its Power Team's name and, when the team has several tables, "2 of 3".
function seating_tables(seats) {
	const tables = new Map();
	seats.forEach((seat) => {
		if (!tables.has(seat.seating_team)) {
			const mixed = seat.team_type === "Mixed";
			tables.set(seat.seating_team, {
				number: tables.size + 1,
				mixed,
				team: mixed ? __("Mixed Power Team") : seat.power_team_name || seat.power_team || seat.seating_team,
				seats: [],
			});
		}
		tables.get(seat.seating_team).seats.push(seat);
	});

	const parts = {};
	tables.forEach((table) => (parts[table.team] = parts[table.team] || []).push(table));
	Object.values(parts).forEach((group) =>
		group.forEach((table, i) => Object.assign(table, { part: i + 1, parts: group.length }))
	);
	return [...tables.values()];
}

const SEATING_CSS = `
	.msa-seating-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 20px; margin-bottom: 16px; }
	.msa-seating-stat { display: flex; align-items: baseline; gap: 6px; color: var(--text-muted); }
	.msa-seating-stat b { font-size: var(--text-xl); color: var(--text-color); }
	.msa-seating-search { margin-left: auto; width: 240px; max-width: 100%; }
	.msa-seating-legend { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 16px; font-size: var(--text-sm); color: var(--text-muted); }
	.msa-seating-legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 3px;
		margin-right: 6px; background: var(--msa-accent); vertical-align: -1px; }
	.msa-seating-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
	.msa-table-card { --msa-accent: var(--blue-500); --msa-tint: var(--blue-50);
		border: 1px solid var(--border-color); border-top: 4px solid var(--msa-accent);
		border-radius: var(--border-radius-md); background: var(--card-bg); overflow: hidden; }
	.msa-table-card.mixed, .msa-seating-legend .mixed { --msa-accent: var(--orange-500); --msa-tint: var(--orange-50); }
	.msa-seating-legend .team { --msa-accent: var(--blue-500); }
	.msa-table-head { display: flex; align-items: center; gap: 12px; padding: 12px 14px; background: var(--msa-tint);
		border-bottom: 1px solid var(--border-color); }
	.msa-table-no { flex-shrink: 0; width: 48px; text-align: center; line-height: 1.1; border-radius: var(--border-radius);
		padding: 5px 0; background: var(--msa-accent); color: #fff; }
	.msa-table-no small { display: block; font-size: 10px; text-transform: uppercase; letter-spacing: .04em; opacity: .85; }
	.msa-table-no b { font-size: 20px; }
	.msa-table-title { min-width: 0; }
	.msa-table-title .msa-team { font-weight: 600; color: var(--text-color); line-height: 1.3; }
	.msa-table-title .msa-meta { font-size: var(--text-sm); color: var(--text-muted); }
	.msa-seat-list { list-style: none; margin: 0; padding: 4px 0; }
	.msa-seat-list li { display: flex; gap: 10px; padding: 7px 14px; }
	.msa-seat-list li + li { border-top: 1px solid var(--border-color); }
	.msa-seat-list li.msa-match { background: var(--yellow-50, #fffbeb); }
	.msa-seat-no { flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%; background: var(--gray-100);
		color: var(--text-muted); font-size: var(--text-xs); font-weight: 600; text-align: center; line-height: 22px; }
	.msa-seat-who { min-width: 0; line-height: 1.35; }
	.msa-seat-who .msa-company { font-size: var(--text-sm); color: var(--text-muted); }
	.msa-seat-who .msa-own-team { display: inline-block; margin-top: 3px; padding: 0 6px; border-radius: 8px;
		font-size: var(--text-xs); background: var(--gray-100); color: var(--text-muted); }
	.msa-seating-none { padding: 24px; text-align: center; color: var(--text-muted); }
`;

function render_seating(frm) {
	const $wrapper = frm.get_field("seating_preview").$wrapper;
	const seats = frm.doc.seats || [];
	if (!seats.length) {
		$wrapper.html(`<div class="msa-seating-none text-muted" style="padding: 24px; text-align: center;">
			${__("No seating yet. Click <b>Generate Seating</b> to seat the Active members at tables.")}</div>`);
		return;
	}

	const esc = frappe.utils.escape_html;
	const tables = seating_tables(seats);
	const mixed_tables = tables.filter((t) => t.mixed).length;
	const stat = (value, label) => `<div class="msa-seating-stat"><b>${value}</b>${label}</div>`;

	const cards = tables.map((table) => {
		const meta = [
			table.mixed ? __("Members from different Power Teams") : __("Power Team"),
			table.parts > 1 ? __("table {0} of {1}", [table.part, table.parts]) : "",
			__("{0} seats", [table.seats.length]),
		].filter(Boolean);
		const rows = table.seats
			.map((seat, i) => {
				const name = seat.member_name || seat.member;
				const own_team = seat.power_team_name || seat.power_team || __("No Power Team");
				return `<li data-search="${esc(`${name} ${seat.company_name || ""}`.toLowerCase())}">
					<span class="msa-seat-no" title="${__("Seat {0}", [i + 1])}">${i + 1}</span>
					<div class="msa-seat-who">
						<b>${esc(name)}</b>
						${seat.company_name ? `<div class="msa-company">${esc(seat.company_name)}</div>` : ""}
						${table.mixed ? `<span class="msa-own-team">${esc(own_team)}</span>` : ""}
					</div>
				</li>`;
			})
			.join("");
		return `<div class="msa-table-card ${table.mixed ? "mixed" : ""}">
			<div class="msa-table-head">
				<div class="msa-table-no"><small>${__("Table")}</small><b>${table.number}</b></div>
				<div class="msa-table-title">
					<div class="msa-team">${esc(table.team)}</div>
					<div class="msa-meta">${meta.join(" &middot; ")}</div>
				</div>
			</div>
			<ol class="msa-seat-list">${rows}</ol>
		</div>`;
	});

	$wrapper.html(`<style>${SEATING_CSS}</style>
		<div class="msa-seating-bar">
			${stat(seats.length, __("members seated"))}
			${stat(tables.length, __("tables"))}
			${stat(frm.doc.members_per_team || "-", __("seats per table"))}
			<input type="search" class="form-control input-sm msa-seating-search" placeholder="${__("Find a member or company...")}">
		</div>
		<div class="msa-seating-legend">
			<span class="team">${__("Power Team table: members of one Power Team ({0})", [tables.length - mixed_tables])}</span>
			<span class="mixed">${__("Mixed table: members left over from several Power Teams ({0})", [mixed_tables])}</span>
		</div>
		<div class="msa-seating-grid">${cards.join("")}</div>
		<div class="msa-seating-none" style="display: none;">${__("No member matches your search.")}</div>`);

	// Search: show only the tables with a matching member, and mark the member
	$wrapper.find(".msa-seating-search").on("input", function () {
		const text = this.value.trim().toLowerCase();
		let shown = 0;
		$wrapper.find(".msa-table-card").each(function () {
			let found = !text;
			$(this).find("li").each(function () {
				const match = !!text && this.dataset.search.includes(text);
				$(this).toggleClass("msa-match", match);
				found = found || match;
			});
			$(this).toggle(found);
			shown += found ? 1 : 0;
		});
		$wrapper.find(".msa-seating-grid + .msa-seating-none").toggle(!shown);
	});
}
