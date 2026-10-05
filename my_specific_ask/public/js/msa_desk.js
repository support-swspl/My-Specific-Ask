// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

// Loaded on every desk page (app_include_js): the Gives badges, shared by the Members list,
// the member form and the home page, and the home page's "Top Givers" block.

// Badge for the Gives a member has listed; highest level first. Fewer than 6 Gives: no badge.
frappe.msa_badges = [
	{ min: 25, label: __("Platinum"), rim: "#d3e3ee", face: "#5f86a3" },
	{ min: 19, label: __("Gold"), rim: "#ffd98a", face: "#f59e0b" },
	{ min: 13, label: __("Silver"), rim: "#e1e4e8", face: "#8d96a3" },
	{ min: 6, label: __("Bronze"), rim: "#e6bd95", face: "#b4682a" },
];

frappe.msa_badge_for = (gives) => frappe.msa_badges.find((badge) => gives >= badge.min);

// The badge as a rosette with a tick: ribbons, a scalloped rim (8 small circles round a big one), the face
frappe.msa_badge_html = (gives, size = 20) => {
	const badge = frappe.msa_badge_for(gives);
	if (!badge) return "";
	const rim_circles = [0, 1, 2, 3, 4, 5, 6, 7]
		.map((i) => {
			const angle = (i * Math.PI) / 4;
			return `<circle cx="${(12 + 6.6 * Math.cos(angle)).toFixed(2)}" cy="${(9.5 + 6.6 * Math.sin(angle)).toFixed(2)}" r="2.4"/>`;
		})
		.join("");
	// Shown when the mouse is over the badge
	const tip = __("{0} badge - {1} Gives", [badge.label, gives]);
	return `<span class="msa-gives-badge" title="${tip}" style="display: inline-flex; flex-shrink: 0; margin-left: 10px; vertical-align: middle;">
		<svg viewBox="0 0 24 24" width="${size}" height="${size}" role="img" aria-label="${tip}">
			<path d="M8.2 13 5 22.5l3.4-1.2 1.9 2.7 2.4-8z" fill="#ff4d4f"/>
			<path d="M15.8 13 19 22.5l-3.4-1.2-1.9 2.7-2.4-8z" fill="#e8383b"/>
			<g fill="${badge.rim}"><circle cx="12" cy="9.5" r="7"/>${rim_circles}</g>
			<circle cx="12" cy="9.5" r="5" fill="${badge.face}"/>
			<path d="M9.5 9.6l1.8 1.8 3.3-3.5" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
		</svg>
	</span>`;
};

// Home page "Your Progress" (a Custom HTML Block set up by setup_home_page in members.py):
// the logged-in member's name, Gives, their badge and how many more Gives the next badge needs.
frappe.msa_my_progress = async function (element) {
	const r = await frappe.call("my_specific_ask.my_specific_ask.doctype.members.members.get_my_progress");
	const me = r.message;
	if (!me) {
		// Admin logins without a member profile have no Gives of their own
		element.innerHTML = `<div class="text-muted">${__("This login has no member profile.")}</div>`;
		return;
	}

	// The login's own name until the member has filled in theirs
	const full_name = frappe.utils.escape_html(me.full_name || frappe.session.user_fullname || "");
	const gives = me.gives_count || 0;
	const badge = frappe.msa_badge_for(gives);
	// The next badge up: the lowest one that needs more Gives than the member has
	const next = [...frappe.msa_badges].reverse().find((b) => b.min > gives);
	// The bar shows the Gives out of what the next badge needs, as the "6 of 13 Gives" under it
	const percent = next ? Math.round((gives / next.min) * 100) : 100;

	const have = badge
		? __("You have {0} Gives — {1} badge.", [gives, badge.label])
		: __("You have {0} Gives.", [gives]);
	const to_go = next
		? __("{0} more for {1}.", [next.min - gives, next.label])
		: __("You have reached the highest badge.");

	element.innerHTML = `
		<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 16px; padding: 16px; background: var(--card-bg);
			border: 1px solid var(--border-color); border-radius: var(--border-radius-md);">
			${badge ? `<span style="margin-left: -10px;">${frappe.msa_badge_html(gives, 44)}</span>` : ""}
			<div style="flex: 1; min-width: 200px;">
				<div style="font-size: var(--text-lg); font-weight: 600; margin-bottom: 4px;">${full_name}</div>
				<div><b>${have}</b> ${to_go}</div>
				<div style="height: 8px; margin-top: 10px; background: var(--gray-200); border-radius: 4px; overflow: hidden;"
					role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}">
					<div style="width: ${percent}%; height: 100%; background: ${(next || badge).face}; border-radius: 4px;"></div>
				</div>
				<div class="text-muted small" style="margin-top: 6px;">
					${next ? __("{0} of {1} Gives", [gives, next.min]) : __("{0} Gives", [gives])}
				</div>
			</div>
			<button class="btn btn-primary btn-sm msa-my-profile">${__("My Profile")}</button>
		</div>`;

	// Their own profile, where the Gives are added
	element.querySelector(".msa-my-profile").addEventListener("click", () => {
		frappe.set_route("Form", "Members", me.name);
	});
};

// Home page "Top Givers" (a Custom HTML Block set up by setup_home_page in members.py):
// the members with the most Gives, each with their badge. Clicking one opens the profile.
frappe.msa_top_givers = async function (element) {
	const r = await frappe.call("my_specific_ask.my_specific_ask.doctype.members.members.get_top_givers");
	const givers = r.message || [];
	if (!givers.length) {
		element.innerHTML = `<div class="text-muted">${__("No Gives have been added yet.")}</div>`;
		return;
	}

	const esc = frappe.utils.escape_html;
	element.innerHTML = givers
		.map(
			(member, i) => `
			<div class="msa-top-giver" data-member="${esc(member.name)}" style="display: flex; align-items: center;
				gap: 12px; padding: 10px 14px; margin-bottom: 8px; cursor: pointer; background: var(--card-bg);
				border: 1px solid var(--border-color); border-radius: var(--border-radius-md);">
				<span class="text-muted" style="width: 18px; font-weight: 600;">${i + 1}</span>
				<span style="flex: 1; min-width: 0;">
					<b>${esc(member.full_name || member.name)}</b>${frappe.msa_badge_html(member.gives_count)}
					<div class="text-muted small ellipsis">${esc(member.company_name || "")}</div>
				</span>
				<span style="white-space: nowrap; font-weight: 600;">${__("{0} Gives", [member.gives_count])}</span>
			</div>`
		)
		.join("");

	element.addEventListener("click", (event) => {
		const row = event.target.closest(".msa-top-giver");
		if (row) frappe.set_route("Form", "Members", row.dataset.member);
	});
};
