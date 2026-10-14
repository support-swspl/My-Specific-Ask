// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Seating Arrangement", {
	refresh(frm) {
		render_seating(frm);
		if (frm.is_new()) {
			frm.set_intro(__("Choose how many members sit in each Power Team, save, then click Generate Seating."), "blue");
			return;
		}
		frm.add_custom_button(__("Generate Seating"), () => generate(frm)).addClass("btn-primary");
	},
});

function generate(frm) {
	const run = () =>
		frm.call({ method: "generate_seating", doc: frm.doc, freeze: true, freeze_message: __("Arranging seats...") })
			.then(() => {
				frm.refresh();
				frappe.show_alert({ message: __("Seating generated"), indicator: "green" });
			});

	const save_then_run = () => (frm.is_dirty() ? frm.save().then(run) : run());
	if (frm.doc.seats && frm.doc.seats.length) {
		frappe.confirm(__("This replaces the current seating with a fresh one. Continue?"), save_then_run);
	} else {
		save_then_run();
	}
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
