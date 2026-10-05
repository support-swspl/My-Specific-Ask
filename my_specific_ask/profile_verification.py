# Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Verification of a member's Profile URL (their public page on their network's website,
e.g. https://bni-puneeast.in/en-IN/memberdetails?encryptedMemberId=...).

Two checks, each with its own tick on the member. Only System Managers see the ticks:
- System: the page is read and its text must have the member's name and their mobile number or company.
- Administrator: a System Manager ticks "Verified by Administrator" by hand. This gives the
  member the blue tick, and from then on the member can no longer change the link.
"""

import ipaddress
import json
import re
import socket
from html import unescape
from urllib.parse import parse_qs, unquote, urlsplit

import frappe
import requests
from frappe import _

# Set by this module only; a member cannot tick these through the form or the API
AUTO_FIELDS = ("system_verified", "verification_remarks")
TIMEOUT = 15
# Of the page's text, what is compared
PAGE_TEXT_LENGTH = 4000
# BNI websites: bni.in, bni-puneeast.in, www.bni-india.in ...
BNI_HOST = re.compile(r"^(www\.)?bni[a-z0-9-]*(\.[a-z0-9-]+)+$")
BROWSER = {"User-Agent": "Mozilla/5.0 (compatible; MySpecificAsk)"}


class CheckFailed(Exception):
	"""A check could not be done; the text is shown in the member's Verification Remarks."""


def validate(doc):
	"""Members validate: keep the ticks honest, lock the Profile URL once an administrator has
	verified it, and clear the System tick when the link changes."""
	from my_specific_ask.my_specific_ask.doctype.members.members import is_admin

	doc.profile_url = (doc.profile_url or "").strip()
	before = doc.get_doc_before_save()

	# What a form or the API sent for these is dropped: the last check's result stays
	for field in AUTO_FIELDS:
		doc.set(field, before.get(field) if before else ("" if field == "verification_remarks" else 0))
	if not is_admin():
		doc.manually_verified = before.manually_verified if before else 0

	if before and (before.profile_url or "") != doc.profile_url:
		# After the System check the member may still correct the link; after an administrator's, not
		if before.manually_verified and not is_admin():
			frappe.throw(_("Your Profile URL has been verified by an administrator and can no longer be changed."))
		# The System tick was for the old page
		doc.system_verified = 0
		doc.verification_remarks = ""


@frappe.whitelist(methods=["POST"])
def verify_now(member: str):
	"""Member form, after a save with a new Profile URL and from an administrator's
	"Verify Profile URL" button: run the System check now."""
	frappe.get_doc("Members", member).check_permission("write")
	return run(member)


def run(member):
	"""Do the System check of `member`'s Profile URL and write the result on the member."""
	doc = frappe.get_doc("Members", member)
	try:
		verified, remark = system_check(doc, get_page_text(doc.profile_url))
	except CheckFailed as e:
		verified, remark = 0, str(e)
	except requests.RequestException:
		frappe.log_error(title="Profile URL: page could not be read")
		verified, remark = 0, _("the page could not be read.")

	result = {"system_verified": verified, "verification_remarks": _("System: {0}").format(remark)}
	# Not a save: validate would put the old tick back. The modified time is left alone,
	# so a form that is open on this member can still be saved.
	frappe.db.set_value("Members", member, result, update_modified=False)
	return result


def get_page_text(url):
	"""The text of the member's page. Only BNI pages can be read: they load the member's
	details with a second request, which is repeated here."""
	parts = urlsplit(url or "")
	host = (parts.hostname or "").lower()
	if parts.scheme != "https" or not BNI_HOST.match(host):
		raise CheckFailed(_("only BNI member pages (https://bni-...) can be checked automatically."))
	check_public_host(host)

	query = parse_qs(parts.query)
	member_id = (query.get("encryptedUserId") or query.get("encryptedMemberId") or [""])[0]
	if not member_id:
		raise CheckFailed(_("the link has no member in it. Copy it from your own member details page."))

	# Redirects are not followed: they could lead to an address inside our own network
	page = requests.get(url, headers=BROWSER, timeout=TIMEOUT, allow_redirects=False)
	if page.status_code != 200:
		raise CheckFailed(_("the page did not open (status {0}).").format(page.status_code))

	def find(pattern):
		match = re.search(pattern, page.text)
		return match.group(1) if match else ""

	data = {
		"parameters": parts.query,
		"pageMode": find(r'var pageMode\s*=\s*"([^"]*)"') or "Live_Site",
		"mappedWidgetSettings": find(r"var mappedWidgetSettings\s*=\s*'([^']*)'"),
		"websitetype": find(r'var websitetype\s*=\s*"([^"]*)"'),
		"website_type": find(r'id="website_type"\s+value="([^"]*)"'),
		"website_id": find(r'id="website_id"\s+value="([^"]*)"'),
		"memberId": unquote(member_id),
	}
	try:
		language = json.loads(find(r"var languages\s*=\s*(\{.*?\});")).get("activeLanguage") or {}
	except ValueError:
		language = {}
	for key, value in language.items():
		data[f"languages[activeLanguage][{key}]"] = value

	details = requests.post(
		f"https://{parts.netloc}/bnicms/v3/frontend/memberdetail/display",
		data=data,
		headers={**BROWSER, "X-Requested-With": "XMLHttpRequest", "Referer": url},
		timeout=TIMEOUT,
		allow_redirects=False,
	)
	if details.status_code != 200:
		raise CheckFailed(_("the member's details did not load (status {0}).").format(details.status_code))

	text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", details.text)
	text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text))).strip()
	if not text:
		raise CheckFailed(_("the page shows no member."))
	return text[:PAGE_TEXT_LENGTH]


def check_public_host(host):
	"""The site's server reads a link a member typed: refuse one that points inside our own network."""
	try:
		addresses = {info[4][0] for info in socket.getaddrinfo(host, 443)}
	except OSError:
		raise CheckFailed(_("the website {0} was not found.").format(host))
	if not all(ipaddress.ip_address(address).is_global for address in addresses):
		raise CheckFailed(_("the website {0} cannot be checked.").format(host))


def system_check(doc, page_text):
	"""(1 or 0, remark): the page must have the member's name, and their mobile number or company."""
	def letters(value):
		return re.sub(r"[^a-z0-9]", "", (value or "").lower())

	page_letters = letters(page_text)
	page_digits = re.sub(r"\D", "", page_text)
	# The last 10 digits: the page may write the number with or without +91
	mobile = re.sub(r"\D", "", doc.mobile_number or "")[-10:]

	matched = {
		_("name"): bool(letters(doc.full_name)) and letters(doc.full_name) in page_letters,
		_("mobile number"): len(mobile) == 10 and mobile in page_digits,
		_("company"): bool(letters(doc.company_name)) and letters(doc.company_name) in page_letters,
	}
	found = [label for label, ok in matched.items() if ok]
	missing = [label for label, ok in matched.items() if not ok]
	verified = matched[_("name")] and (matched[_("mobile number")] or matched[_("company")])

	remark = _("the page has the member's {0}").format(", ".join(found)) if found else _("nothing on the page matches")
	if missing and found:
		remark += _("; not their {0}").format(", ".join(missing))
	return int(verified), remark + "."

