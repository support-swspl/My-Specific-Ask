// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Members", {
	setup(frm) {
		// Power Team dropdown: each team's name with its description under it
		frm.set_query("power_team", () => ({
			query: "my_specific_ask.my_specific_ask.doctype.members.members.power_team_query",
		}));
	},

	refresh(frm) {
		// Frappe puts the team's number (PT-0001) in front of the description: leave it out
		const power_team = frm.fields_dict.power_team;
		if (!power_team.msa_merge_duplicates) {
			power_team.msa_merge_duplicates = power_team.merge_duplicates;
			power_team.merge_duplicates = (results) =>
				power_team.msa_merge_duplicates(results).map((d) => {
					let description = d.description || "";
					if (description === d.value) description = "";
					else if (description.startsWith(d.value + ", ")) description = description.slice(d.value.length + 2);
					return Object.assign(d, { description });
				});
		}

		if (frm.is_new() || frappe.user.has_role("System Manager")) return;

		if (frm.doc.user === frappe.session.user) {
			frm.set_df_property("user", "read_only", 1);
			// Set by boot_session while required fields are still empty (e.g. after sign-up)
			if (frm.doc.name === frappe.boot.msa_incomplete_profile) {
				frm.set_intro(
					__("Welcome! Please fill in all required fields and click Save to start using My Specific Ask."),
					"yellow"
				);
			}
		} else {
			frm.disable_form();
			frm.set_intro(__("You can view this member. Only your own profile is editable."), "blue");
		}
	},

	// Region is always kept in capitals (the server does the same on save)
	region(frm) {
		const region = (frm.doc.region || "").toUpperCase();
		if (region !== frm.doc.region) frm.set_value("region", region);
	},

	before_save(frm) {
		// Gives at the last save, so after_save can tell whether this save reached a badge
		frm.msa_gives_before = frm.doc.gives_count || 0;
	},

	after_save(frm) {
		// Saving means every required field is filled: release the redirect in complete_profile.js
		if (frm.doc.name === frappe.boot.msa_incomplete_profile) {
			frappe.boot.msa_incomplete_profile = null;
			frm.set_intro("");
		}

		// Congratulations with falling sprinkles when this save reached a badge (first at 6 Gives).
		// Same levels as the badges in members_list.js.
		const badges = [
			{ min: 25, label: __("Platinum") },
			{ min: 19, label: __("Gold") },
			{ min: 13, label: __("Silver") },
			{ min: 6, label: __("Bronze") },
		];
		const badge_for = (gives) => badges.find((badge) => gives >= badge.min);
		const gives = frm.doc.gives_count || 0;
		const before = badge_for(frm.msa_gives_before || 0);
		const now = badge_for(gives);
		if (now && (!before || now.min > before.min)) {
			frappe.msa_sprinkles();
			frappe.msgprint({
				title: "🎉 " + __("Congratulations!"),
				indicator: "green",
				message: __("Congratulations! You have just claimed your {0} badge.", [now.label.bold()]),
			});
		}
	},
});

// Celebration for a few seconds: confetti shot from both bottom corners and sprinkles falling from the top
frappe.msa_sprinkles = function () {
	const canvas = document.createElement("canvas");
	// Above the pop-up, and never in the way of a click
	canvas.style.cssText = "position: fixed; inset: 0; pointer-events: none; z-index: 2000;";
	canvas.width = window.innerWidth;
	canvas.height = window.innerHeight;
	document.body.appendChild(canvas);

	const ctx = canvas.getContext("2d");
	const colours = ["#f59e0b", "#ef4444", "#3b82f6", "#10b981", "#a855f7", "#ec4899"];
	const piece = (x, y, vx, vy, gravity) => ({
		x,
		y,
		vx,
		vy,
		gravity,
		width: 6 + Math.random() * 6,
		height: 8 + Math.random() * 8,
		round: Math.random() < 0.3,
		angle: Math.random() * Math.PI,
		spin: Math.random() * 0.3 - 0.15,
		colour: colours[Math.floor(Math.random() * colours.length)],
	});

	// Sprinkles: they start spread out above the screen, so they keep coming for a while
	const pieces = Array.from({ length: 180 }, () =>
		piece(Math.random() * canvas.width, -Math.random() * canvas.height, Math.random() * 2 - 1, 3 + Math.random() * 4, 0)
	);
	// Confetti: a party popper in each bottom corner shoots up and towards the middle, then it falls
	for (const side of [1, -1]) {
		for (let i = 0; i < 120; i++) {
			const power = 12 + Math.random() * 16;
			// 35 to 80 degrees up from the floor
			const aim = ((35 + Math.random() * 45) * Math.PI) / 180;
			pieces.push(
				piece(side === 1 ? 0 : canvas.width, canvas.height, side * power * Math.cos(aim), -power * Math.sin(aim), 0.35)
			);
		}
	}

	const end = Date.now() + 5000;
	const draw = () => {
		ctx.clearRect(0, 0, canvas.width, canvas.height);
		for (const p of pieces) {
			p.vy += p.gravity;
			p.x += p.vx;
			p.y += p.vy;
			p.angle += p.spin;
			ctx.save();
			ctx.translate(p.x, p.y);
			ctx.rotate(p.angle);
			ctx.fillStyle = p.colour;
			if (p.round) {
				ctx.beginPath();
				ctx.arc(0, 0, p.width / 2, 0, 2 * Math.PI);
				ctx.fill();
			} else {
				ctx.fillRect(-p.width / 2, -p.height / 2, p.width, p.height);
			}
			ctx.restore();
		}
		if (Date.now() < end) requestAnimationFrame(draw);
		else canvas.remove();
	};
	draw();
};
