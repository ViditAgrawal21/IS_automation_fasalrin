"""
Claim form automation — fill IS/PRI claim form fields.

Handles:
  - IS Submission Type (COMPLETE / PARTIAL)
  - First Loan Disbursal Date (rmdp date picker)
  - Interest Cycle end / Rollover Date (rmdp date picker)
  - Max Withdrawal Amount
  - Applicable IS Amount
  - Declaration checkbox
"""

from utils.constants import SUBMISSION_TYPE_VALUES


def _set_rmdp_date(page, picker_index: int, date_str: str, log_callback=None):
    """
    Set a date in a React Modern DatePicker (rmdp) input.

    The rmdp-input fields are read-only to normal typing, so we use JS to:
      1. Find the Nth rmdp-input on the page
      2. Set its value via React's internal setter
      3. Dispatch input/change events
      4. If a calendar popup appears, click outside to dismiss it

    Args:
        page: Playwright page.
        picker_index: 0-based index of the rmdp-input on the page.
        date_str: Date string in the format expected by the portal (e.g., "03-04-2023" or "03/04/2023").
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    try:
        # Click the rmdp-input to open the calendar
        rmdp_inputs = page.locator(".rmdp-input")
        count = rmdp_inputs.count()

        if count <= picker_index:
            raise Exception(f"Expected at least {picker_index + 1} date pickers, found {count}")

        target_input = rmdp_inputs.nth(picker_index)
        target_input.wait_for(state="visible", timeout=5000)

        # Try JS approach: set value and fire events
        page.evaluate("""(args) => {
            const [idx, dateVal] = args;
            const inputs = document.querySelectorAll('.rmdp-input');
            const el = inputs[idx];
            if (!el) return;

            // Use React's value setter to bypass read-only
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, dateVal);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));

            // Also try focus + blur to trigger validation
            el.dispatchEvent(new Event('focus', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
        }""", [picker_index, date_str])
        page.wait_for_timeout(150)

        # Verify the value was set
        actual = page.evaluate("""(idx) => {
            const inputs = document.querySelectorAll('.rmdp-input');
            return inputs[idx] ? inputs[idx].value : '';
        }""", picker_index)

        if actual and date_str in actual:
            log(f"Date picker {picker_index + 1} set to: {date_str}")
            return

        # Fallback: click to open, clear, type the date
        log(f"JS set didn't stick, trying click+type approach for picker {picker_index + 1}...")
        target_input.click()
        page.wait_for_timeout(300)

        # Triple-click to select all, then type
        target_input.click(click_count=3)
        page.wait_for_timeout(100)
        target_input.type(date_str, delay=30)
        page.wait_for_timeout(150)

        # Press Enter to confirm and close calendar
        target_input.press("Enter")
        page.wait_for_timeout(150)

        # Click outside to dismiss any remaining calendar popup
        page.click("body", position={"x": 10, "y": 10})
        page.wait_for_timeout(100)

        log(f"Date picker {picker_index + 1} filled: {date_str}")

    except Exception as e:
        raise Exception(f"Could not set date picker {picker_index + 1} to '{date_str}': {e}")


def _set_input_value(page, selector: str, value: str, field_name: str,
                     log_callback=None):
    """
    Set a text input value using JS (React-compatible).

    Args:
        page: Playwright page.
        selector: CSS selector for the input.
        value: Value to set.
        field_name: Human-readable name for logging.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    try:
        page.evaluate("""(args) => {
            const [sel, val] = args;
            const el = document.querySelector(sel);
            if (!el) return;
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""", [selector, value])
        page.wait_for_timeout(100)
        log(f"{field_name}: {value}")
    except Exception as e:
        raise Exception(f"Could not fill {field_name}: {e}")


def _select_dropdown(page, selector: str, value: str, field_name: str,
                     log_callback=None):
    """
    Select a dropdown option by value using JS.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    try:
        page.evaluate("""(args) => {
            const [sel, val] = args;
            const el = document.querySelector(sel);
            if (!el) return;
            el.value = val;
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""", [selector, value])
        page.wait_for_timeout(100)
        log(f"{field_name}: value={value}")
    except Exception as e:
        raise Exception(f"Could not select {field_name}: {e}")


def fill_claim_form(page, row_data: dict, profile: dict, log_callback=None):
    """
    Fill the IS/PRI claim form with data from Excel row and profile.

    Args:
        page: Playwright page.
        row_data: Dict from Excel row (first_disbursal_date, rollover_date, etc.)
        profile: Profile dict (submission_type, etc.)
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    log("Filling claim form...")

    # ── 1. IS Submission Type ──
    submission_type = profile.get("submission_type", "COMPLETE")
    submission_val = SUBMISSION_TYPE_VALUES.get(submission_type, "1")
    _select_dropdown(
        page,
        "select[name='priSubmissionType']",
        submission_val,
        f"IS Submission Type ({submission_type})",
        log_callback=log,
    )

    # ── 2. First Loan Disbursal Date ──
    disbursal_date = row_data.get("first_disbursal_date", "")
    if disbursal_date:
        _set_rmdp_date(page, 0, disbursal_date, log_callback=log)
    else:
        log("Warning: First Loan Disbursal Date is empty")

    # ── 3. Interest Cycle end / Rollover Date ──
    rollover_date = row_data.get("rollover_date", "")
    if rollover_date:
        _set_rmdp_date(page, 1, rollover_date, log_callback=log)
    else:
        log("Warning: Rollover Date is empty")

    # ── 4. Max Withdrawal Amount ──
    max_withdrawal = row_data.get("max_withdrawal", "")
    if max_withdrawal:
        _set_input_value(
            page,
            "input[name='maxWithdrawalAmount']",
            str(max_withdrawal),
            "Max Withdrawal Amount",
            log_callback=log,
        )
    else:
        log("Warning: Max Withdrawal Amount is empty")

    # ── 5. Applicable IS Amount ──
    applicable_is = row_data.get("applicable_is", "")
    if applicable_is:
        _set_input_value(
            page,
            "input[name='applicableISAmount']",
            str(applicable_is),
            "Applicable IS Amount",
            log_callback=log,
        )
    else:
        log("Warning: Applicable IS Amount is empty")

    # ── 6. Declaration Checkbox ──
    try:
        checkbox = page.locator("input#declarationText")
        if checkbox.is_visible(timeout=3000):
            is_checked = checkbox.is_checked()
            if not is_checked:
                checkbox.click()
                page.wait_for_timeout(100)
                log("Declaration checkbox ticked")
            else:
                log("Declaration checkbox already ticked")
        else:
            # Fallback: use JS to check it
            page.evaluate("""() => {
                const cb = document.querySelector("input#declarationText")
                         || document.querySelector("input[name='declarationText']");
                if (cb && !cb.checked) {
                    cb.checked = true;
                    cb.dispatchEvent(new Event('change', { bubbles: true }));
                    cb.dispatchEvent(new Event('click', { bubbles: true }));
                }
            }""")            
            page.wait_for_timeout(100)
            log("Declaration checkbox ticked (JS)")
    except Exception as e:
        raise Exception(f"Could not tick declaration checkbox: {e}")

    log("Claim form filled successfully")
