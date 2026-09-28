import frappe
from my_specific_ask.my_specific_ask.api.matching_engine import get_matches

def get_context(context):
    # 1. Require user to be logged in
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    # 2. Find the BNI Member record linked to the logged-in User
    member_id = frappe.db.get_value("BNI Member", {"user": frappe.session.user}, "name")

    if not member_id:
        context.error_message = "Your user account is not linked to a BNI Member profile yet."
        context.matches = []
        return context

    # 3. Load the member data and matches
    context.member = frappe.get_doc("BNI Member", member_id)
    
    # 4. We reuse the API logic you already wrote!
    context.matches = get_matches(member_id, limit=10)