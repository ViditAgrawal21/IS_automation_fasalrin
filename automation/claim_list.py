"""
Claim list page automation — filter, search, and click ADD.

Handles the claim-application-list page:
  1. Select Financial Year, Claim Type, Claim Status from dropdowns
  2. Click PROCEED
  3. Search by Loan Application Number
  4. Click ADD on the matching row
"""

from utils.constants import (
    CLAIM_LIST_URL,
    CLAIM_TYPE_VALUES,
    CLAIM_STATUS_VALUES,
)


def navigate_to_claim_list(page, log_callback=None):
    """
    Navigate to the Claim Application List page.
    If already on the page, just verify.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    if "/claim-application-list" not in page.url:
        log("Navigating to Claim Application List...")
        page.goto(CLAIM_LIST_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(200)

    log("On Claim Application List page")


def select_filters_and_proceed(page, profile: dict, log_callback=None):
    """
    Select Financial Year, Claim Type, Claim Status and click PROCEED.

    Args:
        page: Playwright page.
        profile: Profile dict with financial_year, claim_type, claim_status.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    fy = profile.get("financial_year", "")
    claim_type = profile.get("claim_type", "IS")
    claim_status = profile.get("claim_status", "PENDING")

    # ── Select Financial Year ──
    log(f"Selecting Financial Year: {fy}")
    try:
        fy_select = page.locator("select[name='financialYear']")
        fy_select.wait_for(state="visible", timeout=10000)

        # Select by visible text — try matching the label text
        page.evaluate("""(fy) => {
            const sel = document.querySelector("select[name='financialYear']");
            if (!sel) return;
            for (const opt of sel.options) {
                if (opt.text.includes(fy) || opt.value.includes(fy)) {
                    sel.value = opt.value;
                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                    break;
                }
            }
        }""", fy)
        page.wait_for_timeout(100)
    except Exception as e:
        raise Exception(f"Could not select Financial Year '{fy}': {e}")

    # ── Select Claim Type ──
    claim_type_val = CLAIM_TYPE_VALUES.get(claim_type, "1")
    log(f"Selecting Claim Type: {claim_type} (value={claim_type_val})")
    try:
        page.evaluate("""(val) => {
            const sel = document.querySelector("select[name='claimType']");
            if (!sel) return;
            sel.value = val;
            sel.dispatchEvent(new Event('change', { bubbles: true }));
        }""", claim_type_val)
        page.wait_for_timeout(100)
    except Exception as e:
        raise Exception(f"Could not select Claim Type '{claim_type}': {e}")

    # ── Select Claim Status ──
    claim_status_val = CLAIM_STATUS_VALUES.get(claim_status, "-1")
    log(f"Selecting Claim Status: {claim_status} (value={claim_status_val})")
    try:
        page.evaluate("""(val) => {
            const sel = document.querySelector("select[name='claimStatus']");
            if (!sel) return;
            sel.value = val;
            sel.dispatchEvent(new Event('change', { bubbles: true }));
        }""", claim_status_val)
        page.wait_for_timeout(100)
    except Exception as e:
        raise Exception(f"Could not select Claim Status '{claim_status}': {e}")

    # ── Click PROCEED ──
    log("Clicking PROCEED...")
    try:
        proceed_btn = page.locator("button.genGreenBtn:has-text('PROCEED')").first
        proceed_btn.wait_for(state="visible", timeout=5000)
        proceed_btn.click()
        page.wait_for_timeout(400)
        log("PROCEED clicked — loading claim list")
    except Exception as e:
        raise Exception(f"Could not click PROCEED: {e}")

    # Wait for the table or search area to appear
    try:
        page.wait_for_selector(
            "input[type='search'], table, .table-responsive",
            timeout=15000
        )
        log("Claim list loaded")
    except Exception:
        log("Warning: Could not confirm claim list loaded, continuing...")


def search_loan_application(page, loan_app_no: str, log_callback=None):
    """
    Search for a Loan Application Number in the claim list.

    Args:
        page: Playwright page.
        loan_app_no: The Loan Application Number to search.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    log(f"Searching for Loan Application: {loan_app_no}")

    # ── Fill search input ──
    try:
        search_input = page.locator("input[type='search']").first
        search_input.wait_for(state="visible", timeout=10000)

        # Clear previous search and enter new value
        search_input.click()
        search_input.fill("")
        page.wait_for_timeout(100)

        # Use JS to set value for React compatibility
        page.evaluate("""(val) => {
            const el = document.querySelector("input[type='search']");
            if (!el) return;
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""", loan_app_no)
        page.wait_for_timeout(100)
    except Exception as e:
        raise Exception(f"Could not fill search input: {e}")

    # ── Click Search button ──
    try:
        search_btn = page.locator("button.btn-secondary").first
        if search_btn.is_visible(timeout=3000):
            search_btn.click()
            page.wait_for_timeout(400)
            log("Search executed")
        else:
            # Some portals auto-search on input, press Enter as fallback
            search_input.press("Enter")
            page.wait_for_timeout(400)
            log("Search executed (Enter key)")
    except Exception:
        # Fallback: press Enter
        try:
            search_input = page.locator("input[type='search']").first
            search_input.press("Enter")
            page.wait_for_timeout(400)
            log("Search executed (Enter fallback)")
        except Exception as e:
            raise Exception(f"Could not execute search: {e}")


def click_add_button(page, log_callback=None):
    """
    Click the ADD button on the matching row in the claim list table.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    log("Clicking ADD button...")

    try:
        # Primary selector: the green ADD button
        add_btn = page.locator("button.edit-greenbtn:has-text('ADD')").first
        if not add_btn.is_visible(timeout=5000):
            # Fallback: try broader selector
            add_btn = page.locator("button:has-text('ADD')").first

        add_btn.wait_for(state="visible", timeout=10000)
        add_btn.click()
        page.wait_for_timeout(400)
        log("ADD clicked — claim form loading")
    except Exception as e:
        raise Exception(
            f"Could not click ADD button. The loan application may not exist "
            f"in the claim list or search returned no results. Error: {e}"
        )

    # Wait for claim form to appear
    try:
        page.wait_for_selector(
            "select[name='priSubmissionType'], input[name='maxWithdrawalAmount']",
            timeout=15000
        )
        log("Claim form loaded")
    except Exception:
        log("Warning: Could not confirm claim form loaded, continuing...")
