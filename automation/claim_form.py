"""
Claim form automation — fill IS/PRI claim form fields.

Page flow:
  1. Select IS Submission Type (COMPLETE / PARTIAL)
  2. First Loan Disbursal / Interest Cycle Start Date  (rmdp calendar)
  3. Interest Cycle end / Rollover Date                 (rmdp calendar)
  4. Max Withdrawal Amount                              (text input)
  5. (Maximum Allowed Claim — auto-calculated, skip)
  6. Applicable IS Amount                               (text input)
  7. Declaration checkbox
"""

from utils.constants import SUBMISSION_TYPE_VALUES

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


# ═══════════════════════════════════════════════════════════════
# Date helpers
# ═══════════════════════════════════════════════════════════════

def _parse_date(date_str: str):
    """Parse DD-MM-YYYY or DD/MM/YYYY into (day, month, year) ints."""
    parts = date_str.replace("/", "-").split("-")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _parse_header_text(header_text: str):
    """Parse 'April, 2022' → (4, 2022).  Returns (None, None) on failure."""
    if not header_text:
        return None, None
    text = header_text.lower().replace(",", " ")
    month_num = None
    year = None
    for part in text.split():
        p = part.strip()
        if p in MONTH_NAMES:
            month_num = MONTH_NAMES[p]
        elif p.isdigit() and len(p) == 4:
            year = int(p)
    return month_num, year


# ═══════════════════════════════════════════════════════════════
# Calendar operations — scoped to a specific .rmdp-container
# ═══════════════════════════════════════════════════════════════

def _close_any_calendar(page):
    """Close any lingering rmdp calendar popup by blurring & clicking away."""
    page.evaluate("""() => {
        if (document.activeElement) document.activeElement.blur();
        var h = document.querySelector('h1,h2,h3,h4,h5,h6,.heading,.card-header');
        if (h) h.click();
    }""")
    page.wait_for_timeout(100)


def _set_rmdp_date(page, picker_index: int, date_str: str, log=None):
    """
    Set a date in a React Modern DatePicker by navigating the calendar UI.

    All operations are scoped to the specific .rmdp-container at picker_index,
    so multiple calendars in the DOM don't interfere with each other.

    Steps:
      1. Click input inside the container → opens that container's calendar
      2. Read header from that container → navigate arrows to target month/year
      3. Click the target day inside that container → calendar auto-closes
    """
    target_day, target_month, target_year = _parse_date(date_str)

    _close_any_calendar(page)
    page.wait_for_timeout(100)

    # ── Find the specific .rmdp-container ──
    containers = page.locator(".rmdp-container")
    needed = picker_index + 1
    for _ in range(30):
        if containers.count() >= needed:
            break
        page.wait_for_timeout(200)
    if containers.count() < needed:
        raise Exception(f"Need ≥{needed} .rmdp-container elements, found {containers.count()}")

    container = containers.nth(picker_index)

    # ── Click the input to open the calendar popup ──
    input_el = container.locator(".rmdp-input")
    input_el.wait_for(state="visible", timeout=5000)
    input_el.click(force=True)
    page.wait_for_timeout(400)

    # ── Confirm calendar is open (header readable within this container) ──
    header_loc = container.locator(".rmdp-header-values")
    for _ in range(20):
        try:
            txt = header_loc.text_content(timeout=300)
            m, y = _parse_header_text(txt)
            if m is not None and y is not None:
                break
        except Exception:
            pass
        page.wait_for_timeout(150)
    else:
        # retry click
        input_el.click(force=True)
        page.wait_for_timeout(500)

    # ── Navigate to the target month/year ──
    arrow_containers = container.locator(".rmdp-arrow-container")
    # DOM order: first = left (<), last = right (>)

    for _ in range(150):
        try:
            txt = header_loc.text_content(timeout=300)
        except Exception:
            txt = ""
        cur_m, cur_y = _parse_header_text(txt)
        if cur_m is None or cur_y is None:
            page.wait_for_timeout(150)
            continue
        if cur_y == target_year and cur_m == target_month:
            break
        if (target_year, target_month) < (cur_y, cur_m):
            arrow_containers.first.click(force=True)    # left arrow
        else:
            arrow_containers.last.click(force=True)     # right arrow
        page.wait_for_timeout(100)
    else:
        raise Exception(f"Could not navigate calendar to {target_month}/{target_year}")

    # ── Click the target day ──
    clicked = container.evaluate("""(el, day) => {
        var days = el.querySelectorAll('.rmdp-day:not(.rmdp-deactive) span');
        for (var i = 0; i < days.length; i++) {
            if (days[i].textContent.trim() === String(day)) {
                days[i].click();
                return true;
            }
        }
        return false;
    }""", target_day)
    if not clicked:
        raise Exception(f"Could not find day {target_day} in calendar")

    page.wait_for_timeout(200)
    if log:
        log(f"Date picker {picker_index + 1} → {date_str}")


# ═══════════════════════════════════════════════════════════════
# Text input setter (React-compatible)
# ═══════════════════════════════════════════════════════════════

def _set_input_value(page, selector: str, value: str, field_name: str,
                     log=None):
    """
    Set a text input value via the React nativeInputValueSetter trick.
    Waits for the field to exist and be enabled before writing.
    """
    # Wait for field to be ready (present + enabled), max ~6 s
    for _ in range(30):
        state = page.evaluate("""(sel) => {
            var el = document.querySelector(sel);
            if (!el) return 'missing';
            if (el.disabled) return 'disabled';
            return 'ready';
        }""", selector)
        if state == "ready":
            break
        page.wait_for_timeout(200)

    page.evaluate("""(args) => {
        var sel = args[0], val = args[1];
        var el = document.querySelector(sel);
        if (!el) return;
        el.focus();
        var setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
        setter.call(el, val);
        el.dispatchEvent(new Event('input',  { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.blur();
    }""", [selector, value])
    page.wait_for_timeout(50)

    if log:
        log(f"{field_name}: {value}")


# ═══════════════════════════════════════════════════════════════
# Dropdown selector
# ═══════════════════════════════════════════════════════════════

def _select_dropdown(page, value: str, field_name: str, log=None):
    """
    Select the IS Submission Type dropdown.
    Tries multiple possible selectors for the <select> element.
    """
    selectors = [
        "select[name='priSubmissionType']",
        "select[name='isSubmissionType']",
        "select[name='submissionType']",
        "select",                                       # last resort
    ]
    for sel in selectors:
        try:
            dd = page.locator(sel).first
            if dd.is_visible(timeout=1000):
                dd.select_option(value=value)
                page.wait_for_timeout(50)
                if log:
                    log(f"{field_name}: value={value}")
                return
        except Exception:
            continue

    # JS fallback on first <select>
    page.evaluate("""(val) => {
        var el = document.querySelector('select');
        if (!el) return;
        var setter = Object.getOwnPropertyDescriptor(
            window.HTMLSelectElement.prototype, 'value').set;
        setter.call(el, val);
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }""", value)
    page.wait_for_timeout(50)
    if log:
        log(f"{field_name}: value={value} (JS fallback)")


# ═══════════════════════════════════════════════════════════════
# Portal validation error detection
# ═══════════════════════════════════════════════════════════════

def _check_form_errors(page, log=None):
    """
    Detect inline validation errors shown by the portal after filling fields.
    E.g. "Max Withdrawal Amount should be less than equal to total Loan sanctioned amount."
    If found, raise an exception so the row is skipped.
    """
    errors = page.evaluate("""() => {
        var msgs = [];
        // Tooltip / popover error messages (the red tooltip in screenshot)
        var tooltips = document.querySelectorAll(
            '.tooltip-inner, .popover-body, [role="tooltip"], .error-message, '
            + '.invalid-feedback, .form-error, .text-danger, .field-error'
        );
        for (var i = 0; i < tooltips.length; i++) {
            var t = tooltips[i].textContent.trim();
            if (t) msgs.push(t);
        }
        // Inputs with red border / error class that have a title attribute
        var inputs = document.querySelectorAll(
            'input.is-invalid, input.error, input[aria-invalid="true"], '
            + 'input.border-danger, input[style*="border-color: red"], '
            + 'input[style*="border-color: rgb(255"]'
        );
        for (var j = 0; j < inputs.length; j++) {
            var title = inputs[j].getAttribute('title') || '';
            if (title) msgs.push(title);
        }
        // Warning triangle icons with adjacent/parent text
        var warns = document.querySelectorAll(
            '.fa-exclamation-triangle, .fa-warning, .warning-icon, '
            + 'svg.text-danger, i.text-danger'
        );
        for (var k = 0; k < warns.length; k++) {
            var parent = warns[k].closest('div, span, td');
            if (parent) {
                var pt = parent.getAttribute('title')
                      || parent.getAttribute('data-original-title')
                      || '';
                if (pt) msgs.push(pt);
            }
        }
        // Any visible element containing known error phrases
        var body = document.body.innerText || '';
        var patterns = [
            'should be less than',
            'should be greater than',
            'must be less than',
            'must be greater than',
            'cannot exceed',
            'exceeds the',
            'is required',
            'invalid amount',
        ];
        for (var p = 0; p < patterns.length; p++) {
            if (body.toLowerCase().includes(patterns[p])) {
                // Find the exact element
                var all = document.querySelectorAll('div, span, p, label, small');
                for (var a = 0; a < all.length; a++) {
                    var txt = all[a].textContent.trim();
                    if (txt.toLowerCase().includes(patterns[p]) && txt.length < 200) {
                        msgs.push(txt);
                        break;
                    }
                }
            }
        }
        // Deduplicate
        return [...new Set(msgs)];
    }""")

    if errors:
        error_text = "; ".join(errors)
        if log:
            log(f"PORTAL VALIDATION ERROR: {error_text}")
        raise Exception(f"Portal validation error: {error_text}")


# ═══════════════════════════════════════════════════════════════
# Declaration checkbox
# ═══════════════════════════════════════════════════════════════

def _tick_declaration(page, log=None):
    """Tick the declaration checkbox (React-compatible click)."""
    page.evaluate("""() => {
        var cb = document.querySelector("input#declarationText")
              || document.querySelector("input[name='declarationText']")
              || document.querySelector("input[type='checkbox']");
        if (cb && !cb.checked) {
            cb.click();                       // .click() triggers React onChange
        }
    }""")
    page.wait_for_timeout(200)
    if log:
        log("Declaration checkbox ticked")


# ═══════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════

def fill_claim_form(page, row_data: dict, profile: dict, log_callback=None):
    """
    Fill the IS claim form with Excel data and profile settings.

    Sequence:
      1. IS Submission Type   → dropdown
      2. First Disbursal Date → rmdp calendar
      3. Rollover Date        → rmdp calendar
      4. Max Withdrawal       → text input
      5. (Maximum Allowed auto-calculated — skip)
      6. Applicable IS        → text input
      7. Declaration checkbox  → click
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    log("Filling claim form...")

    # ── 1. IS Submission Type ──────────────────────────────────
    submission_type = profile.get("submission_type", "COMPLETE")
    submission_val = SUBMISSION_TYPE_VALUES.get(submission_type, "1")
    _select_dropdown(page, submission_val,
                     f"IS Submission Type ({submission_type})", log)

    # React re-render after dropdown — date pickers appear
    page.wait_for_timeout(500)

    # ── 2. First Loan Disbursal Date ──────────────────────────
    disbursal_date = row_data.get("first_disbursal_date", "")
    if disbursal_date:
        _set_rmdp_date(page, 0, disbursal_date, log)
    else:
        log("WARNING: First Disbursal Date is empty")

    # Rollover field unlocks after disbursal is filled
    page.wait_for_timeout(500)

    # ── 3. Interest Cycle end / Rollover Date ─────────────────
    rollover_date = row_data.get("rollover_date", "")
    if rollover_date:
        _set_rmdp_date(page, 1, rollover_date, log)
    else:
        log("WARNING: Rollover Date is empty")

    # Amount fields unlock after both dates are filled
    page.wait_for_timeout(500)

    # ── 4. Max Withdrawal Amount ──────────────────────────────
    max_withdrawal = row_data.get("max_withdrawal", "")
    if max_withdrawal:
        _set_input_value(page, "input[name='maxWithdrawalAmount']",
                         str(max_withdrawal), "Max Withdrawal Amount", log)
    else:
        log("WARNING: Max Withdrawal Amount is empty")

    # Wait for auto-calculation of Maximum Allowed Claim
    page.wait_for_timeout(500)

    # ── 5. Applicable IS Amount ───────────────────────────────
    applicable_is = row_data.get("applicable_is", "")
    if applicable_is:
        _set_input_value(page, "input[name='applicableISAmount']",
                         str(applicable_is), "Applicable IS Amount", log)
    else:
        log("WARNING: Applicable IS Amount is empty")

    page.wait_for_timeout(300)

    # ── 6. Check for portal validation errors ─────────────────
    _check_form_errors(page, log)

    # ── 7. Declaration Checkbox ───────────────────────────────
    _tick_declaration(page, log)

    log("Claim form filled successfully")
