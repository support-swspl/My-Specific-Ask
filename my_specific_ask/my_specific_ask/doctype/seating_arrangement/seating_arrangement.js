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

function render_seating(frm) {
	const $wrapper = frm.get_field("seating_preview").$wrapper;
	const seats = frm.doc.seats || [];
	if (!seats.length) {
		$wrapper.html(`<div class="text-muted">${__("No seating yet.")}</div>`);
		return;
	}

	const teams = new Map();
	seats.forEach((seat) => {
		if (!teams.has(seat.seating_team)) teams.set(seat.seating_team, { type: seat.team_type, seats: [] });
		teams.get(seat.seating_team).seats.push(seat);
	});

	const cards = [...teams].map(([name, team]) => {
		const mixed = team.type === "Mixed";
		const rows = team.seats
			.map(
				(seat, i) => `<tr>
					<td class="text-muted" style="width:24px;">${i + 1}</td>
					<td><b>${frappe.utils.escape_html(seat.member_name || seat.member)}</b>
						<div class="text-muted small">${frappe.utils.escape_html(seat.company_name || "")}</div></td>
					${mixed ? `<td class="text-muted small text-right">${frappe.utils.escape_html(seat.power_team_name || seat.power_team || __("No Power Team"))}</td>` : ""}
				</tr>`
			)
			.join("");
		return `<div class="col-md-4 col-sm-6" style="margin-bottom:16px;">
			<div style="border:1px solid var(--border-color);border-radius:var(--border-radius-md);padding:12px;height:100%;">
				<div class="flex justify-between align-center" style="margin-bottom:8px;">
					<b>${frappe.utils.escape_html(name)}</b>
					<span class="indicator-pill ${mixed ? "orange" : "blue"}">${team.seats.length} ${__("members")}</span>
				</div>
				<table class="table table-sm" style="margin:0;">${rows}</table>
			</div>
		</div>`;
	});

	$wrapper.html(`<div class="row">${cards.join("")}</div>`);
}
