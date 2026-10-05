// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
// For license information, please see license.txt

// A comment was added above every line on 2026-10-03; [2026-10-03] marks the parts written that day.
// Register the scripts for the Members form
frappe.ui.form.on("Members", {
	// setup runs once, when the form is first created
	setup(frm) {
		// Power Team dropdown: each team's name with its description under it
		// [2026-10-03] Tell the Power Team field to get its dropdown options
		frm.set_query("power_team", () => ({
			// from our own server function, which also returns each team's description
			query: "my_specific_ask.my_specific_ask.doctype.members.members.power_team_query",
		}));
	},

	// refresh runs every time the form is shown or reloaded
	refresh(frm) {
		// Frappe puts the team's number (PT-0001) in front of the description: leave it out
		// [2026-10-03] The Power Team field on this form
		const power_team = frm.fields_dict.power_team;
		// Only do this once per form
		if (!power_team.msa_merge_duplicates) {
			// Keep Frappe's original function that tidies the dropdown results
			power_team.msa_merge_duplicates = power_team.merge_duplicates;
			// Replace it with our own version:
			power_team.merge_duplicates = (results) =>
				// run the original first, then go through each dropdown option
				power_team.msa_merge_duplicates(results).map((d) => {
					// The small text under the option (the team's number, then its description)
					let description = d.description || "";
					// If it is only the team's number, show nothing
					if (description === d.value) description = "";
					// If it starts with the number and a comma, cut that part off
					else if (description.startsWith(d.value + ", ")) description = description.slice(d.value.length + 2);
					// Put the cleaned text back on the option
					return Object.assign(d, { description });
				});
		}

		// [2026-10-05] Profile URL verification (the checks are in profile_verification.py)
		// Whether an administrator is looking at the form
		const is_admin = frappe.user.has_role("System Manager");
		// The two ticks and the remarks are in a section only administrators see (set in the doctype).
		// Once an administrator has verified the Profile URL, the member can no longer change it;
		// the server refuses it too
		frm.set_df_property("profile_url", "read_only", !is_admin && frm.doc.manually_verified ? 1 : 0);
		// The title area at the top of the form
		const $title = frm.page.$title_area.find(".title-text");
		// Take away a tick put there by an earlier refresh
		$title.find(".msa-verified").remove();
		// Blue tick after the member's name once an administrator has verified them (public/js/msa_desk.js)
		$title.append(frappe.msa_verified_html(frm.doc.manually_verified, 18));
		// A saved profile with a Profile URL, seen by an administrator:
		if (!frm.is_new() && frm.doc.profile_url && is_admin) {
			// a button to run the System check again, e.g. after the name or mobile number was corrected
			frm.add_custom_button(__("Verify Profile URL"), () => frappe.msa_verify_profile_url(frm));
		}

		// New (unsaved) forms and System Managers need none of the rules below
		if (frm.is_new() || is_admin) return;

		// The member is looking at their own profile:
		if (frm.doc.user === frappe.session.user) {
			// they may not change which login the profile belongs to
			frm.set_df_property("user", "read_only", 1);
			// Set by boot_session while required fields are still empty (e.g. after sign-up)
			if (frm.doc.name === frappe.boot.msa_incomplete_profile) {
				// Show a yellow welcome message at the top of the form
				frm.set_intro(
					// The message text
					__("Welcome! Please fill in all required fields and click Save to start using My Specific Ask."),
					// The colour of the message
					"yellow"
				);
			}
		// Somebody else's profile:
		} else {
			// make the whole form read-only
			frm.disable_form();
			// and say why in a blue message
			frm.set_intro(__("You can view this member. Only your own profile is editable."), "blue");
		}
	},

	// Region is always kept in capitals (the server does the same on save)
	// [2026-10-03] Runs when the Region field is changed
	region(frm) {
		// The typed text in capital letters
		const region = (frm.doc.region || "").toUpperCase();
		// If that differs from what is in the field, write the capitals back
		if (region !== frm.doc.region) frm.set_value("region", region);
	},

	// [2026-10-03] Runs just before the form is saved
	before_save(frm) {
		// Gives at the last save, so after_save can tell whether this save reached a badge
		frm.msa_gives_before = frm.doc.gives_count || 0;
	},

	// Runs after the form was saved successfully
	after_save(frm) {
		// Saving means every required field is filled: release the redirect in complete_profile.js
		if (frm.doc.name === frappe.boot.msa_incomplete_profile) {
			// Forget the "incomplete profile" marker, so the member is no longer sent back here
			frappe.boot.msa_incomplete_profile = null;
			// Remove the welcome message
			frm.set_intro("");
		}

		// [2026-10-05] A new or changed Profile URL has no remarks yet (the server clears them): check it now
		if (frm.doc.profile_url && !frm.doc.verification_remarks) frappe.msa_verify_profile_url(frm);

		// Congratulations with falling sprinkles when this save reached a badge (first at 6 Gives).
		// The badges are in public/js/msa_desk.js.
		// [2026-10-03] The badge the member had before this save
		const before = frappe.msa_badge_for(frm.msa_gives_before || 0);
		// The badge the member has now
		const now = frappe.msa_badge_for(frm.doc.gives_count || 0);
		// Celebrate only when there is a badge now and it is higher than before
		if (now && (!before || now.min > before.min)) {
			// Start the confetti and sprinkles
			frappe.msa_sprinkles();
			// Show the congratulations pop-up
			frappe.msgprint({
				// The pop-up title, with a party emoji
				title: "🎉 " + __("Congratulations!"),
				// A green dot beside the title
				indicator: "green",
				// The pop-up text, with the badge name in bold
				message: __("Congratulations! You have just claimed your {0} badge.", [now.label.bold()]),
			});
		}
	},
});

// [2026-10-05] Runs the System check of the member's Profile URL. An administrator sees the result
// in a pop-up; for a member it runs unseen after their save.
frappe.msa_verify_profile_url = function (frm) {
	// Whether an administrator is looking at the form
	const is_admin = frappe.user.has_role("System Manager");
	// Unsaved changes would be lost by the reload below, and the checks use what is saved
	if (frm.is_dirty()) {
		// Say so and stop
		frappe.show_alert({ message: __("Please save the profile first."), indicator: "orange" });
		return;
	}
	// Ask the server to read the page and compare it with the profile
	frappe.call({
		// The server function that does both checks
		method: "my_specific_ask.profile_verification.verify_now",
		// Which member to check
		args: { member: frm.doc.name },
		// For an administrator, grey out the screen while it runs (it reads a website, which takes some seconds)
		freeze: is_admin,
		// The text shown meanwhile
		freeze_message: __("Checking the Profile URL..."),
		// When the answer is back:
		callback: (r) => {
			// The result: the System tick and the remarks
			const result = r.message || {};
			// Only an administrator is told the result
			if (is_admin) {
				frappe.msgprint({
					// The pop-up title
					title: __("Profile URL check"),
					// The dot beside the title: green when the check passed, orange otherwise
					indicator: result.system_verified ? "green" : "orange",
					// The remarks; they contain text from outside, so it is escaped
					message: frappe.utils.escape_html(result.verification_remarks || ""),
				});
			}
			// Load the member again so the form has the new tick and remarks
			frm.reload_doc();
		},
	});
};

// Celebration for a few seconds: confetti shot from both bottom corners and sprinkles falling from the top
// [2026-10-03] The function that draws the celebration
frappe.msa_sprinkles = function () {
	// Create a drawing layer (canvas)
	const canvas = document.createElement("canvas");
	// Above the pop-up, and never in the way of a click
	canvas.style.cssText = "position: fixed; inset: 0; pointer-events: none; z-index: 2000;";
	// Make the layer as wide as the window
	canvas.width = window.innerWidth;
	// and as tall as the window
	canvas.height = window.innerHeight;
	// Add it to the page
	document.body.appendChild(canvas);

	// The tool used to draw on the layer
	const ctx = canvas.getContext("2d");
	// The six colours a piece can have
	const colours = ["#f59e0b", "#ef4444", "#3b82f6", "#10b981", "#a855f7", "#ec4899"];
	// Makes one piece of paper from its start position (x, y), its speed sideways (vx) and downwards (vy), and its gravity
	const piece = (x, y, vx, vy, gravity) => ({
		// Position from the left
		x,
		// Position from the top
		y,
		// Speed sideways per frame
		vx,
		// Speed downwards per frame (negative means upwards)
		vy,
		// How much faster it falls each frame
		gravity,
		// Width between 6 and 12 pixels
		width: 6 + Math.random() * 6,
		// Height between 8 and 16 pixels
		height: 8 + Math.random() * 8,
		// About 3 in 10 pieces are round dots, the rest are strips
		round: Math.random() < 0.3,
		// Starting rotation
		angle: Math.random() * Math.PI,
		// How fast it spins, in either direction
		spin: Math.random() * 0.3 - 0.15,
		// A random colour from the list
		colour: colours[Math.floor(Math.random() * colours.length)],
	});

	// Sprinkles: they start spread out above the screen, so they keep coming for a while
	// Make 180 of them
	const pieces = Array.from({ length: 180 }, () =>
		// each at a random place across the width, somewhere above the screen, with a slight sideways drift, falling speed 3 to 7 and no gravity
		piece(Math.random() * canvas.width, -Math.random() * canvas.height, Math.random() * 2 - 1, 3 + Math.random() * 4, 0)
	);
	// Confetti: a party popper in each bottom corner shoots up and towards the middle, then it falls
	// Once for the left corner (1) and once for the right corner (-1)
	for (const side of [1, -1]) {
		// 120 pieces from each corner
		for (let i = 0; i < 120; i++) {
			// How hard this piece is shot
			const power = 12 + Math.random() * 16;
			// 35 to 80 degrees up from the floor
			const aim = ((35 + Math.random() * 45) * Math.PI) / 180;
			// Add the piece to the list:
			pieces.push(
				// it starts in the bottom corner, flies up and towards the middle, and gravity 0.35 pulls it back down
				piece(side === 1 ? 0 : canvas.width, canvas.height, side * power * Math.cos(aim), -power * Math.sin(aim), 0.35)
			);
		}
	}

	// The animation stops 5 seconds from now
	const end = Date.now() + 5000;
	// Draws one frame of the animation
	const draw = () => {
		// Wipe the previous frame
		ctx.clearRect(0, 0, canvas.width, canvas.height);
		// For every piece:
		for (const p of pieces) {
			// gravity makes it fall faster
			p.vy += p.gravity;
			// move it sideways
			p.x += p.vx;
			// move it down (or up)
			p.y += p.vy;
			// turn it a little
			p.angle += p.spin;
			// Remember the drawing position
			ctx.save();
			// Move the drawing position to the piece
			ctx.translate(p.x, p.y);
			// Rotate to the piece's angle
			ctx.rotate(p.angle);
			// Use the piece's colour
			ctx.fillStyle = p.colour;
			// A round piece:
			if (p.round) {
				// start a shape
				ctx.beginPath();
				// a circle as wide as the piece
				ctx.arc(0, 0, p.width / 2, 0, 2 * Math.PI);
				// fill it with the colour
				ctx.fill();
			// A strip of paper:
			} else {
				// draw a filled rectangle centred on the piece
				ctx.fillRect(-p.width / 2, -p.height / 2, p.width, p.height);
			}
			// Put the drawing position back
			ctx.restore();
		}
		// While the 5 seconds are not over, draw the next frame
		if (Date.now() < end) requestAnimationFrame(draw);
		// otherwise remove the layer from the page
		else canvas.remove();
	};
	// Draw the first frame
	draw();
};

// [2026-10-03] A "Save" button in the pop-up that edits one Give or Ask row. The pop-up has no
// Save of its own, so changes were lost when the profile's Save was forgotten after closing it.
// The same script is set for both child tables
for (const child_table of ["Members Give", "Members Ask"]) {
	// Register the script for this child table
	frappe.ui.form.on(child_table, {
		// form_render runs each time the pop-up of a row is opened
		form_render(frm, cdt, cdn) {
			// The row's data, to know which table of the profile it is in
			const row_doc = locals[cdt][cdn];
			// The row of that table that is open now
			const grid_row = frm.fields_dict[row_doc.parentfield].grid.get_row(cdn);
			// The group of buttons in the pop-up's heading, which stays in view and also shows on phones
			const $actions = grid_row.grid_form.wrapper.find(".grid-form-heading .row-actions");
			// The pop-up is built once per row: when the button is already there, do nothing
			if ($actions.find(".msa-save-row").length) return;
			// Put a dark "Save" button first in the group (Frappe hides the group on a read-only profile)
			$actions.prepend(`<button class="btn btn-primary btn-sm pull-right msa-save-row">${__("Save")}</button>`);
			// When the button is clicked:
			$actions.find(".msa-save-row").on("click", () => {
				// close the pop-up, which writes what was typed into the table,
				grid_row.toggle_view(false);
				// save the whole profile,
				frm.save();
				// and stop the click from reaching the heading, which would open the pop-up again
				return false;
			});
		},
	});
}
