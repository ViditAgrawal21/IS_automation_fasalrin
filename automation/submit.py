"""
Submit automation - SAVE & CONTINUE, SUBMIT, and extract Claim ID.

Portal uses Bootstrap modals (.myapp-sucess.modal.show) with:
  - OK / CONFIRM button: button.green-btn
  - CANCEL button: button.outline-btn
  - Modal body text: .modal-body h4

Handles:
  1. Click SAVE & CONTINUE -> dismiss success modal (OK)
  2. Click SUBMIT on preview page -> confirm modal (CONFIRM)
  3. Wait for submitted-successfully modal -> extract Claim ID -> dismiss (OK)
"""

import re

# -- Selectors matching the actual portal modal structure --
MODAL_VISIBLE = ".modal.show"
MODAL_OK_BTN = ".modal.show .modal-body button.green-btn"
SWAL_POPUP = ".swal2-popup"
SWAL_CONFIRM = "button.swal2-confirm"


def _read_modal_text(page):
    """Read text from any visible modal (Bootstrap or SweetAlert2)."""
    return page.evaluate("""() => {
        var h4 = document.querySelector('.modal.show .modal-body h4');
        if (h4 && h4.textContent.trim()) return h4.textContent.trim();
        var mb = document.querySelector('.modal.show .modal-body');
        if (mb && mb.textContent.trim()) return mb.textContent.trim();
        var sw = document.querySelector('.swal2-html-container, .swal2-content');
        if (sw && sw.textContent.trim()) return sw.textContent.trim();
        return '';
    }""")


def _click_modal_ok(page):
    """Click OK / CONFIRM / Close on any visible modal using JS click."""
    # Primary: JS click — bypasses Playwright overlay interception completely
    clicked = page.evaluate("""() => {
        var selectors = [
            '.modal.show .modal-body button.green-btn',
            '.modal.show button.green-btn',
            '.swal2-confirm',
            '.modal.show button'
        ];
        for (var i = 0; i < selectors.length; i++) {
            var btn = document.querySelector(selectors[i]);
            if (btn && btn.offsetParent !== null) {
                btn.click();
                return true;
            }
        }
        return false;
    }""")
    if clicked:
        return True

    # Fallback: Playwright locator click with force
    for selector in [
        MODAL_OK_BTN,
        SWAL_CONFIRM,
        ".modal.show button:has-text('OK')",
        "button:has-text('OK')",
    ]:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=300):
                btn.click(force=True)
                return True
        except Exception:
            continue
    return False


def _wait_for_modal_gone(page, timeout=5000):
    """Wait for any modal to disappear from DOM."""
    try:
        page.wait_for_selector(MODAL_VISIBLE, state="hidden", timeout=timeout)
    except Exception:
        pass
    try:
        page.wait_for_selector(SWAL_POPUP, state="hidden", timeout=1000)
    except Exception:
        pass


def save_and_continue(page, log_callback=None):
    """Click SAVE & CONTINUE and handle the success modal."""
    def log(msg):
        if log_callback:
            log_callback(msg)

    log("Clicking SAVE & CONTINUE...")

    try:
        save_btn = page.locator("button.genGreenBtn:has-text('SAVE & CONTINUE')").first
        save_btn.wait_for(state="visible", timeout=5000)

        for _ in range(20):
            disabled = save_btn.get_attribute("disabled")
            if disabled is None:
                break
            page.wait_for_timeout(50)

        save_btn.click()
    except Exception as e:
        raise Exception(f"Could not click SAVE & CONTINUE: {e}")

    # Wait for the success modal
    try:
        page.wait_for_selector(
            MODAL_VISIBLE + ", " + SWAL_POPUP, timeout=10000
        )
        page.wait_for_timeout(300)
    except Exception:
        log("Warning: No modal detected after SAVE & CONTINUE")

    modal_text = _read_modal_text(page)
    if "saved successfully" in (modal_text or "").lower():
        log(f"SAVE & CONTINUE success: {(modal_text or '')[:100]}")
    elif modal_text:
        log(f"SAVE & CONTINUE modal: {modal_text[:100]}")
        if any(kw in modal_text.lower() for kw in ["error", "fail", "invalid"]):
            _click_modal_ok(page)
            raise Exception(f"Portal error on SAVE: {modal_text[:200]}")

    # Dismiss the modal — retry until it's actually gone
    for dismiss_attempt in range(5):
        _click_modal_ok(page)
        page.wait_for_timeout(500)
        still_visible = page.evaluate(
            """() => !!document.querySelector('.modal.show')"""
        )
        if not still_visible:
            break

    # Wait for modal to fully disappear
    _wait_for_modal_gone(page, timeout=5000)

    # Let React render the preview/review page
    page.wait_for_timeout(1000)


def submit_claim(page, log_callback=None):
    """Click SUBMIT on the preview/review page and handle confirmation."""
    def log(msg):
        if log_callback:
            log_callback(msg)

    log("Clicking SUBMIT...")

    # Dismiss any lingering modal from SAVE step before proceeding
    lingering = page.evaluate(
        """() => !!document.querySelector('.modal.show')"""
    )
    if lingering:
        log("Lingering modal detected — dismissing before SUBMIT...")
        _click_modal_ok(page)
        _wait_for_modal_gone(page, timeout=5000)
        page.wait_for_timeout(500)

    submit_btn = page.locator("button.genGreenBtn:has-text('SUBMIT')").first
    try:
        submit_btn.wait_for(state="visible", timeout=10000)
    except Exception as e:
        raise Exception(f"SUBMIT button not found on preview page: {e}")

    for _ in range(30):
        disabled = submit_btn.get_attribute("disabled")
        if disabled is None:
            break
        page.wait_for_timeout(200)

    page.wait_for_timeout(500)

    # Click SUBMIT with retry (JS click to bypass any remaining overlay) (JS click to bypass any remaining overlay)
    confirmation_appeared = False
    for attempt in range(3):
        # Use JS click as primary — immune to overlay interception
        page.evaluate("""() => {
            var btns = document.querySelectorAll('button.genGreenBtn');
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].textContent.trim().includes('SUBMIT')) {
                    btns[i].click();
                    return;
                }
            }
        }""")
        log(f"SUBMIT clicked (attempt {attempt + 1})")

        try:
            page.wait_for_selector(MODAL_VISIBLE, timeout=5000)
            modal_text = _read_modal_text(page)
            if modal_text:
                confirmation_appeared = True
                log(f"Confirmation dialog: {modal_text[:80]}")
                break
        except Exception:
            # Also check SweetAlert2
            try:
                page.wait_for_selector(SWAL_POPUP, timeout=1000)
                confirmation_appeared = True
                modal_text = _read_modal_text(page)
                log(f"Confirmation dialog (swal): {(modal_text or '')[:80]}")
                break
            except Exception:
                pass
            if attempt < 2:
                log("No confirmation dialog - retrying SUBMIT click...")
                page.wait_for_timeout(1000)

    if not confirmation_appeared:
        raise Exception(
            "SUBMIT button clicked 3 times but no confirmation dialog appeared. "
            "The claim may still be in DRAFT."
        )

    # Click CONFIRM using JS click (reliable inside modal)
    page.wait_for_timeout(300)
    confirmed = page.evaluate("""() => {
        var selectors = [
            '.modal.show .modal-body button.green-btn',
            '.modal.show button.green-btn',
            '.modal.show button'
        ];
        for (var i = 0; i < selectors.length; i++) {
            var btns = document.querySelectorAll(selectors[i]);
            for (var j = 0; j < btns.length; j++) {
                var txt = btns[j].textContent.trim().toUpperCase();
                if (txt === 'CONFIRM' || txt === 'YES' || txt === 'OK') {
                    btns[j].click();
                    return true;
                }
            }
        }
        return false;
    }""")

    if confirmed:
        log("CONFIRM clicked - waiting for server response...")
    else:
        raise Exception("Could not find CONFIRM button on confirmation dialog")

    # Wait for the submission success modal
    for _ in range(30):
        page.wait_for_timeout(500)
        try:
            modal_text = _read_modal_text(page)
            if modal_text and "submitted" in modal_text.lower():
                log(f"SUBMIT success: {modal_text[:120]}")
                return
            if modal_text and any(kw in modal_text.lower()
                                  for kw in ["error", "fail", "unable",
                                              "already", "duplicate"]):
                _click_modal_ok(page)
                raise Exception(f"Portal error: {modal_text[:200]}")
        except Exception as e:
            if "Portal error" in str(e):
                raise
    else:
        log("WARNING: Did not detect 'submitted successfully' modal after CONFIRM")


def extract_claim_id(page, log_callback=None) -> str:
    """
    Extract the Claim ID from the submission success modal.

    Expected: "Claim application No. XXXXXXXXXXX has been submitted successfully."
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    log("Extracting Claim ID...")

    modal_text = _read_modal_text(page)

    if modal_text:
        claim_id = _parse_claim_id(modal_text)
        if claim_id:
            log(f"Claim ID extracted: {claim_id}")
            _click_modal_ok(page)
            _wait_for_modal_gone(page)
            return claim_id

    # Fallback: wait for modal if not yet visible
    try:
        page.wait_for_selector(
            MODAL_VISIBLE + ", " + SWAL_POPUP, timeout=10000
        )
        page.wait_for_timeout(300)
        modal_text = _read_modal_text(page)
        if modal_text:
            claim_id = _parse_claim_id(modal_text)
            if claim_id:
                log(f"Claim ID extracted (attempt 2): {claim_id}")
                _click_modal_ok(page)
                _wait_for_modal_gone(page)
                return claim_id
    except Exception:
        pass

    _click_modal_ok(page)
    _wait_for_modal_gone(page)
    log("WARNING: Could not extract Claim ID from modal")
    return "SUBMITTED (ID not extracted)"


def _parse_claim_id(text):
    """
    Parse Claim ID from the submission success modal text.
    Only extracts from text that contains "submitted".
    """
    if not text or "submitted" not in text.lower():
        return ""

    match = re.search(
        r'[Cc]laim\s+[Aa]pplication\s+[Nn]o\.?\s*([A-Za-z0-9\-]+)',
        text
    )
    if match:
        return match.group(1).strip()

    match = re.search(r'\b(\d{7,})\b', text)
    if match:
        return match.group(1).strip()

    return ""
