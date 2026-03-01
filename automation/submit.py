"""
Submit automation — SAVE & CONTINUE, SUBMIT, and extract Claim ID.

Handles:
  1. Click SAVE & CONTINUE → handle success modal
  2. Click SUBMIT on preview page → handle confirmation modal
  3. Extract Claim ID from success message
"""

import re


def save_and_continue(page, log_callback=None):
    """
    Click SAVE & CONTINUE and handle the success modal.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    log("Clicking SAVE & CONTINUE...")

    try:
        save_btn = page.locator("button.genGreenBtn:has-text('SAVE & CONTINUE')").first
        save_btn.wait_for(state="visible", timeout=10000)

        # Wait for the button to become enabled (form must be valid)
        for _ in range(30):
            disabled = save_btn.get_attribute("disabled")
            if disabled is None:
                break
            page.wait_for_timeout(200)

        save_btn.click()
        page.wait_for_timeout(100)
    except Exception as e:
        raise Exception(f"Could not click SAVE & CONTINUE: {e}")

    # ── Handle success modal ──
    # SweetAlert2 style modal with OK button
    try:
        _handle_modal(page, log, expected_text="saved successfully",
                      action_name="SAVE & CONTINUE")
    except Exception as e:
        # Check for error modal
        _check_error_modal(page, log)
        raise


def submit_claim(page, log_callback=None):
    """
    Click SUBMIT on the preview/review page.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    log("Clicking SUBMIT...")

    # Wait for the preview/review page to fully load after SAVE & CONTINUE
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(500)

    try:
        submit_btn = page.locator("button.genGreenBtn:has-text('SUBMIT')").first
        submit_btn.wait_for(state="visible", timeout=15000)
        submit_btn.click()
        page.wait_for_timeout(100)
    except Exception as e:
        raise Exception(f"Could not click SUBMIT: {e}")

    # ── Handle confirmation dialog (if any "Are you sure?" prompt) ──
    try:
        # SweetAlert2 confirmation: Yes/OK button
        confirm_btn = page.locator(
            "button.swal2-confirm, "
            ".swal2-actions button:has-text('Yes'), "
            ".swal2-actions button:has-text('OK')"
        ).first
        if confirm_btn.is_visible(timeout=2000):
            confirm_btn.click()
            page.wait_for_timeout(100)
            log("Confirmation accepted")
    except Exception:
        pass  # No confirmation dialog, that's fine

    # ── Handle success modal ──
    try:
        _handle_modal(page, log, expected_text="submitted successfully",
                      action_name="SUBMIT")
    except Exception as e:
        _check_error_modal(page, log)
        raise


def extract_claim_id(page, log_callback=None) -> str:
    """
    Extract the Claim ID from the success modal text.

    Expected modal text pattern:
      "Claim application No. XXXXXXXXXXX has been submitted successfully."

    Returns:
        The extracted Claim ID string.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    log("Extracting Claim ID...")

    # Try multiple approaches to find the claim ID

    # Approach 1: Read SweetAlert2 modal content
    try:
        modal_text = page.evaluate("""() => {
            // SweetAlert2 content
            const swalContent = document.querySelector(
                '.swal2-html-container, .swal2-content, #swal2-content, #swal2-html-container'
            );
            if (swalContent) return swalContent.textContent || '';

            // Generic modal content
            const modal = document.querySelector('.modal-body, .modal-content');
            if (modal) return modal.textContent || '';

            return '';
        }""")

        if modal_text:
            claim_id = _parse_claim_id(modal_text)
            if claim_id:
                log(f"Claim ID extracted: {claim_id}")
                # Click OK to dismiss modal
                _click_ok_button(page)
                return claim_id
    except Exception:
        pass

    # Approach 2: Read the full page text for claim IDs
    try:
        page_text = page.evaluate("""() => {
            return document.body ? document.body.innerText : '';
        }""")

        if page_text:
            claim_id = _parse_claim_id(page_text)
            if claim_id:
                log(f"Claim ID extracted from page: {claim_id}")
                _click_ok_button(page)
                return claim_id
    except Exception:
        pass

    # Approach 3: Wait for modal to appear, then extract
    try:
        page.wait_for_selector(
            ".swal2-html-container, .swal2-content, .modal-body",
            timeout=10000
        )
        modal_text = page.locator(
            ".swal2-html-container, .swal2-content, .modal-body"
        ).first.text_content()

        if modal_text:
            claim_id = _parse_claim_id(modal_text)
            if claim_id:
                log(f"Claim ID extracted (attempt 3): {claim_id}")
                _click_ok_button(page)
                return claim_id
    except Exception:
        pass

    # Could not extract — still click OK and return placeholder
    _click_ok_button(page)
    log("WARNING: Could not extract Claim ID from modal")
    return "SUBMITTED (ID not extracted)"


def _parse_claim_id(text: str) -> str:
    """
    Parse Claim ID from modal text.

    Patterns tried:
      - "Claim application No. 12345678901 has been submitted"
      - "Claim application No. ABC-123-XYZ"
      - Any long number/alphanumeric sequence near "Claim"
    """
    if not text:
        return ""

    # Pattern 1: "Claim application No. XXXX has been submitted"
    match = re.search(
        r'[Cc]laim\s+[Aa]pplication\s+[Nn]o\.?\s*([A-Za-z0-9\-]+)',
        text
    )
    if match:
        return match.group(1).strip()

    # Pattern 2: "Application No. XXXX" (more generic)
    match = re.search(
        r'[Aa]pplication\s+[Nn]o\.?\s*([A-Za-z0-9\-]+)',
        text
    )
    if match:
        return match.group(1).strip()

    # Pattern 3: Long numeric string (likely an ID)
    match = re.search(r'\b(\d{8,15})\b', text)
    if match:
        return match.group(1).strip()

    return ""


def _handle_modal(page, log, expected_text: str, action_name: str):
    """
    Wait for a success modal containing `expected_text`, log it, and click OK.
    """
    try:
        # Wait for SweetAlert2 popup
        page.wait_for_selector(
            ".swal2-popup, .swal2-container, .modal.show",
            timeout=15000
        )
        page.wait_for_timeout(50)

        # Read modal text
        modal_text = page.evaluate("""() => {
            const el = document.querySelector(
                '.swal2-html-container, .swal2-content, .modal-body'
            );
            return el ? el.textContent || '' : '';
        }""")

        if expected_text.lower() in (modal_text or "").lower():
            log(f"{action_name} success: {modal_text.strip()[:100]}")
        else:
            log(f"{action_name} modal: {modal_text.strip()[:100]}")

    except Exception:
        log(f"Warning: No modal detected after {action_name}")

    # Always click OK to dismiss the modal so the page can proceed
    _click_ok_button(page)
    page.wait_for_timeout(300)


def _click_ok_button(page):
    """
    Click OK / Close button on any visible modal.
    """
    for selector in [
        "button.swal2-confirm",
        ".swal2-actions button:has-text('OK')",
        ".swal2-actions button:has-text('Ok')",
        "button:has-text('OK')",
        "button:has-text('Close')",
    ]:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=1000):
                btn.click()
                page.wait_for_timeout(30)
                return
        except Exception:
            continue


def _check_error_modal(page, log):
    """
    Check for portal error modals and raise descriptive error.
    """
    try:
        modal_text = page.evaluate("""() => {
            const el = document.querySelector(
                '.swal2-html-container, .swal2-content, .modal-body, .error-message'
            );
            return el ? el.textContent || '' : '';
        }""")

        if modal_text:
            error_keywords = ["error", "fail", "invalid", "unable", "already",
                              "duplicate", "exist"]
            text_lower = modal_text.lower()
            if any(kw in text_lower for kw in error_keywords):
                log(f"PORTAL ERROR: {modal_text.strip()[:200]}")
                _click_ok_button(page)
                raise Exception(f"Portal error: {modal_text.strip()[:200]}")
    except Exception as e:
        if "Portal error" in str(e):
            raise
