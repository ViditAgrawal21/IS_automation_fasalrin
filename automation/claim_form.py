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
    """Parse 'April, 2022' or 'April2022' or 'April 2022' → (4, 2022)."""
    if not header_text:
        return None, None
    text = header_text.lower().replace(",", " ")
    month_num = None
    year = None
    # Try splitting by whitespace first
    for part in text.split():
        p = part.strip()
        if p in MONTH_NAMES:
            month_num = MONTH_NAMES[p]
        elif p.isdigit() and len(p) == 4:
            year = int(p)
    # If no split worked, try matching month name anywhere in the text
    if month_num is None or year is None:
        import re
        for name, num in MONTH_NAMES.items():
            if name in text:
                month_num = num
                break
        year_match = re.search(r'(\d{4})', text)
        if year_match:
            year = int(year_match.group(1))
    return month_num, year


# ═══════════════════════════════════════════════════════════════
# Calendar operations — scoped to a specific .rmdp-container
# ═══════════════════════════════════════════════════════════════

def _close_any_calendar(page):
    """Close any lingering rmdp calendar popup with a real trusted mouse click outside."""
    page.evaluate("() => { if (document.activeElement) document.activeElement.blur(); }")
    safe = page.locator("h1#skipcontent, h1, .card-header, .card-title").first
    try:
        box = safe.bounding_box()
        if box:
            page.mouse.click(box["x"] + box["width"] / 2,
                             box["y"] + box["height"] / 2)
        else:
            page.mouse.click(10, 10)
    except Exception:
        page.mouse.click(10, 10)
    page.wait_for_timeout(200)


def _set_rmdp_date(page, picker_index: int, date_str: str, log=None):
    """
    Set a date in a React Modern DatePicker.

    Tries multiple strategies in order:
      A) Type date directly into the input field (bypasses calendar UI)
      B) nativeInputValueSetter + React change event
      C) Calendar UI navigation + page.mouse.click at bounding-box coords
    """
    target_day, target_month, target_year = _parse_date(date_str)
    formatted = f"{target_day:02d}/{target_month:02d}/{target_year}"
    if log:
        log(f"Calendar {picker_index+1}: setting {formatted}")

    _close_any_calendar(page)

    # ── Find the specific .rmdp-container ──
    containers = page.locator(".rmdp-container")
    needed = picker_index + 1
    for _ in range(15):
        if containers.count() >= needed:
            break
        page.wait_for_timeout(50)
    if containers.count() < needed:
        raise Exception(f"Need ≥{needed} .rmdp-container elements, found {containers.count()}")

    container = containers.nth(picker_index)

    # ── Get the input and wait for it to be enabled ──
    input_el = container.locator(".rmdp-input")
    input_el.wait_for(state="visible", timeout=3000)

    for _wait in range(40):
        disabled = input_el.evaluate("el => el.disabled || el.readOnly")
        if not disabled:
            break
        page.wait_for_timeout(100)

    # ══════════════════════════════════════════════════════════
    # Strategy A: Type the date directly into the input field
    # ══════════════════════════════════════════════════════════
    input_el.click(force=True)
    page.wait_for_timeout(200)
    page.keyboard.press("Control+a")
    page.keyboard.press("Delete")
    page.wait_for_timeout(100)
    input_el.press_sequentially(formatted, delay=50)
    page.wait_for_timeout(400)

    input_val = input_el.evaluate("el => el.value")
    if input_val:
        _close_any_calendar(page)
        if log:
            log(f"Date picker {picker_index+1} → {input_val} (typed)")
        return

    if log:
        log(f"Calendar {picker_index+1}: typing didn't set value, trying nativeInputValueSetter...")

    # ══════════════════════════════════════════════════════════
    # Strategy B: nativeInputValueSetter + React synthetic event
    # ══════════════════════════════════════════════════════════
    container.evaluate("""(c, val) => {
        var input = c.querySelector('.rmdp-input');
        var setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, val);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }""", formatted)
    page.wait_for_timeout(500)

    input_val = input_el.evaluate("el => el.value")
    if input_val:
        _close_any_calendar(page)
        if log:
            log(f"Date picker {picker_index+1} → {input_val} (nativeSetter)")
        return

    if log:
        log(f"Calendar {picker_index+1}: nativeSetter didn't persist, trying calendar UI...")

    # ══════════════════════════════════════════════════════════
    # Strategy C: Calendar UI navigation + mouse click
    # ══════════════════════════════════════════════════════════
    _close_any_calendar(page)
    input_el.click(force=True)
    page.wait_for_timeout(300)

    # Verify calendar popup appeared
    header_loc = container.locator(".rmdp-header-values")
    cal_open = False
    for attempt in range(8):
        try:
            txt = header_loc.text_content(timeout=300)
            m, y = _parse_header_text(txt)
            if m is not None and y is not None:
                cal_open = True
                break
        except Exception:
            pass
        input_el.click(force=True)
        page.wait_for_timeout(400)

    if not cal_open:
        raise Exception(
            f"Calendar {picker_index+1} popup did not open — "
            f"field may be disabled/locked. Check if previous date was set correctly."
        )

    if log:
        log(f"Calendar {picker_index+1}: header reads '{txt}' → {m}/{y}")

    # Navigate to the target month/year
    arrow_containers = container.locator(".rmdp-arrow-container")

    for step in range(150):
        try:
            txt = header_loc.text_content(timeout=300)
        except Exception:
            txt = ""
        cur_m, cur_y = _parse_header_text(txt)
        if cur_m is None or cur_y is None:
            page.wait_for_timeout(50)
            continue
        if cur_y == target_year and cur_m == target_month:
            break
        direction = "left" if (target_year, target_month) < (cur_y, cur_m) else "right"
        if direction == "left":
            arrow_containers.first.click(force=True)
        else:
            arrow_containers.last.click(force=True)
        for _w in range(30):
            page.wait_for_timeout(30)
            try:
                new_txt = header_loc.text_content(timeout=100)
            except Exception:
                new_txt = txt
            if new_txt != txt:
                break
        else:
            if direction == "left":
                arrow_containers.first.click()
            else:
                arrow_containers.last.click()
            page.wait_for_timeout(100)
    else:
        if log:
            try:
                final_txt = header_loc.text_content(timeout=300)
            except Exception:
                final_txt = "(unreadable)"
            log(f"Calendar STUCK: header='{final_txt}', target={target_month}/{target_year}")
        raise Exception(f"Could not navigate calendar to {target_month}/{target_year}")

    # Find the target day and check if it's disabled
    day_divs = container.locator(".rmdp-day:not(.rmdp-deactive)")
    target_day_el = None
    target_span_el = None
    actual_day = target_day

    for i in range(day_divs.count()):
        day_div = day_divs.nth(i)
        span = day_div.locator("span")
        try:
            txt = span.text_content(timeout=100)
        except Exception:
            continue
        if txt.strip() == str(target_day):
            target_day_el = day_div
            target_span_el = span
            break

    if target_day_el is None:
        raise Exception(f"Could not find day {target_day} in calendar")

    # Check if the day is disabled (rmdp uses .rmdp-disabled class)
    day_classes = target_day_el.evaluate("el => el.className")

    if "rmdp-disabled" in day_classes:
        if log:
            log(f"Calendar {picker_index+1}: day {target_day} is DISABLED — "
                f"finding first enabled day in this month...")
        # Find the first enabled (non-disabled, non-deactive) day
        all_days = container.locator(".rmdp-day:not(.rmdp-deactive):not(.rmdp-disabled)")
        found_enabled = False
        for j in range(all_days.count()):
            en_div = all_days.nth(j)
            en_span = en_div.locator("span")
            try:
                en_txt = en_span.text_content(timeout=100).strip()
            except Exception:
                continue
            if en_txt.isdigit():
                actual_day = int(en_txt)
                target_day_el = en_div
                target_span_el = en_span
                found_enabled = True
                if log:
                    log(f"Calendar {picker_index+1}: using first enabled day → {actual_day}")
                break
        if not found_enabled:
            raise Exception(
                f"No enabled days in calendar for {target_month}/{target_year}. "
                f"All dates appear disabled."
            )

    # Click the day using page.mouse at bounding box
    box = target_span_el.bounding_box()
    if box:
        page.mouse.click(box["x"] + box["width"] / 2,
                         box["y"] + box["height"] / 2)
    else:
        target_day_el.click(force=True)

    page.wait_for_timeout(300)
    input_val = input_el.evaluate("el => el.value")

    if not input_val:
        if log:
            log(f"Calendar {picker_index+1}: mouse.click didn't register, trying fiber...")
        # Walk React fiber tree and invoke onClick directly
        fiber_result = container.evaluate("""(el, day) => {
            var dayDivs = el.querySelectorAll('.rmdp-day:not(.rmdp-deactive)');
            for (var i = 0; i < dayDivs.length; i++) {
                var span = dayDivs[i].querySelector('span');
                if (!span || span.textContent.trim() !== String(day)) continue;
                var targets = [dayDivs[i], span];
                for (var t = 0; t < targets.length; t++) {
                    var node = targets[t];
                    var keys = Object.keys(node);
                    var propKey = keys.find(function(k) { return k.startsWith('__reactProps$'); });
                    if (propKey) {
                        var props = node[propKey];
                        if (props && typeof props.onClick === 'function') {
                            props.onClick(new MouseEvent('click', {bubbles:true}));
                            return 'reactProps_' + t;
                        }
                    }
                    var fiberKey = keys.find(function(k) {
                        return k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$');
                    });
                    if (fiberKey) {
                        var cur = node[fiberKey];
                        while (cur) {
                            var p = cur.memoizedProps || cur.pendingProps;
                            if (p && typeof p.onClick === 'function') {
                                p.onClick(new MouseEvent('click', {bubbles:true}));
                                return 'fiber_' + t;
                            }
                            cur = cur.return;
                        }
                    }
                }
                return 'no_handler';
            }
            return 'not_found';
        }""", actual_day)
        if log:
            log(f"Calendar {picker_index+1}: fiber result = {fiber_result}")
        page.wait_for_timeout(400)
        input_val = input_el.evaluate("el => el.value")

    if not input_val and log:
        log(f"Calendar {picker_index+1}: WARNING — input still empty after all strategies")

    _close_any_calendar(page)
    if log:
        log(f"Date picker {picker_index+1} → {actual_day:02d}/{target_month:02d}/{target_year}")


# ═══════════════════════════════════════════════════════════════
# Text input setter (React-compatible)
# ═══════════════════════════════════════════════════════════════

def _set_input_value(page, selector: str, value: str, field_name: str,
                     log=None):
    """
    Set a text input value via the React nativeInputValueSetter trick.
    Waits for the field to exist and be enabled before writing.
    """
    # Wait for field to be ready (present + enabled)
    for _ in range(20):
        state = page.evaluate("""(sel) => {
            var el = document.querySelector(sel);
            if (!el) return 'missing';
            if (el.disabled) return 'disabled';
            return 'ready';
        }""", selector)
        if state == "ready":
            break
        page.wait_for_timeout(50)

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
    page.wait_for_timeout(50)
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
    page.wait_for_timeout(150)

    # ── 2. First Loan Disbursal Date ──────────────────────────
    disbursal_date = row_data.get("first_disbursal_date", "")
    if disbursal_date:
        _set_rmdp_date(page, 0, disbursal_date, log)
    else:
        log("WARNING: First Disbursal Date is empty")

    # Rollover field unlocks after disbursal is filled — must wait for React
    page.wait_for_timeout(500)

    # ── 3. Interest Cycle end / Rollover Date ─────────────────
    rollover_date = row_data.get("rollover_date", "")
    if rollover_date:
        _set_rmdp_date(page, 1, rollover_date, log)
    else:
        log("WARNING: Rollover Date is empty")

    # Amount fields unlock after both dates are filled
    page.wait_for_timeout(100)

    # ── 4. Max Withdrawal Amount ──────────────────────────────
    max_withdrawal = row_data.get("max_withdrawal", "")
    if max_withdrawal:
        _set_input_value(page, "input[name='maxWithdrawalAmount']",
                         str(max_withdrawal), "Max Withdrawal Amount", log)
    else:
        log("WARNING: Max Withdrawal Amount is empty")

    # Wait for auto-calculation of Maximum Allowed Claim
    page.wait_for_timeout(100)

    # ── 5. Applicable IS Amount ───────────────────────────────
    applicable_is = row_data.get("applicable_is", "")
    if applicable_is:
        _set_input_value(page, "input[name='applicableISAmount']",
                         str(applicable_is), "Applicable IS Amount", log)
    else:
        log("WARNING: Applicable IS Amount is empty")

    page.wait_for_timeout(100)

    # ── 6. Check for portal validation errors ─────────────────
    _check_form_errors(page, log)

    # ── 7. Declaration Checkbox ───────────────────────────────
    _tick_declaration(page, log)

    log("Claim form filled successfully")
