"""
Main automation controller — orchestrates the entire IS Claim flow.

Flow per row:
  1. Navigate to Claim Application List
  2. Select filters (FY, Claim Type, Claim Status) → PROCEED
  3. Search by Loan Application Number
  4. Click ADD
  5. Fill claim form (submission type, dates, amounts, declaration)
  6. SAVE & CONTINUE
  7. SUBMIT
  8. Extract Claim ID
  9. Write Claim ID to Excel
  10. Move to next row (if Multi mode)

Supports:
  - Single mode (one row) and Multi mode (batch processing)
  - Stop control via threading.Event()
  - Force-stop via browser process kill
  - Error handling with screenshots
  - Live log callbacks to UI
"""

import threading
import subprocess
import os
from datetime import datetime

from automation.browser import start_browser, close_browser, take_screenshot


class AutomationStoppedError(Exception):
    """Raised when the user requests stop."""
    pass


def _check_stop(stop_event, log=None):
    """Check if stop has been requested and raise if so."""
    if stop_event is not None and stop_event.is_set():
        if log:
            log("STOP signal detected — aborting immediately...")
        raise AutomationStoppedError("Stopped by user")


def force_kill_browser(browser_ref: dict):
    """Force-kill the browser process."""
    try:
        b = browser_ref.get("browser")
        p = browser_ref.get("p")
        if b:
            try:
                b.close()
            except Exception:
                pass
        if p:
            try:
                p.stop()
            except Exception:
                pass
    except Exception:
        pass

    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "chromium.exe", "/T"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "chrome.exe", "/T"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
        )
    except Exception:
        pass


from automation.login import perform_login
from automation.claim_list import (
    navigate_to_claim_list,
    select_filters_and_proceed,
    search_loan_application,
    click_add_button,
)
from automation.claim_form import fill_claim_form
from automation.submit import save_and_continue, submit_claim, extract_claim_id

from excel_engine.reader import load_workbook, read_claim_row, get_total_rows, has_claim_id
from excel_engine.validator import validate_row
from excel_engine.writer import ExcelWriteSession

from utils.logger import log_info, log_error


def _reset_page_for_next_row(page, log):
    """
    Reset the browser page to a clean state between rows.
    Navigates back to the claim application list.
    """
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass

    # Click OK / Close on any lingering dialog
    for txt in ["OK", "Close", "×"]:
        try:
            btn = page.locator(f"button:has-text('{txt}')").first
            if btn.is_visible(timeout=200):
                btn.click()
        except Exception:
            pass

    # Navigate back to claim application list
    try:
        from utils.constants import CLAIM_LIST_URL
        page.goto(CLAIM_LIST_URL, wait_until="domcontentloaded")
        log("Reset — back on Claim Application List")
    except Exception as e:
        log(f"Warning — page reset: {e}")


def run(profile: dict, profile_name: str, excel_path: str, mode: str,
        start_row: int, stop_event: threading.Event, log_callback=None,
        captcha_callback=None, browser_ref: dict = None):
    """
    Main automation entry point for IS Claim processing.

    Args:
        profile: Decrypted profile dict.
        profile_name: Profile name (for session management).
        excel_path: Path to the Excel file.
        mode: 'single' or 'multi'.
        start_row: First data row to process (1-based, minimum 2).
        stop_event: Threading event for stop control.
        log_callback: Function to send log messages to UI.
        captcha_callback: Function to request captcha input from UI.
        browser_ref: Shared dict for force-kill access.
    """
    if browser_ref is None:
        browser_ref = {}

    def log(msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {msg}"
        if log_callback:
            log_callback(full_msg)
        log_info(msg)

    def check():
        _check_stop(stop_event, log)

    p = None
    browser = None
    writer = None

    try:
        # ── Step 1: Load Excel ──
        log("Loading Excel file...")
        ws = load_workbook(excel_path)
        total_rows = get_total_rows(ws)
        log(f"Excel loaded — {total_rows - 1} data rows found (rows 2 to {total_rows})")

        writer = ExcelWriteSession(excel_path, save_interval=5)
        log("Excel write session ready")

        if start_row < 2:
            start_row = 2
        if start_row > total_rows:
            log(f"Start row {start_row} exceeds data rows ({total_rows}). Nothing to process.")
            return

        check()

        # ── Step 2: Launch Browser ──
        log("Launching browser...")
        p, browser, context, page = start_browser(profile_name=profile_name, headless=False)
        browser_ref["p"] = p
        browser_ref["browser"] = browser
        log("Browser launched")

        check()

        # ── Step 3: Login ──
        perform_login(
            page=page,
            context=context,
            profile=profile,
            profile_name=profile_name,
            captcha_callback=captcha_callback,
            log_callback=log,
        )

        check()

        # ── Step 4: Navigate and select filters (once) ──
        navigate_to_claim_list(page, log_callback=log)
        check()

        select_filters_and_proceed(page, profile, log_callback=log)
        check()

        # ── Step 5: Process Rows ──
        end_row = start_row + 1 if mode == "single" else total_rows + 1
        success_count = 0
        fail_count = 0

        for row_num in range(start_row, end_row):
            check()

            log(f"{'═' * 50}")
            log(f"Processing Row {row_num} of {total_rows}")
            log(f"{'═' * 50}")

            try:
                # Skip rows that already have Claim ID
                if has_claim_id(ws, row_num):
                    existing_id = ws.cell(row=row_num, column=7).value
                    log(f"Row {row_num} already processed — Claim ID: {existing_id}. Skipping.")
                    continue

                # ── Validate Row ──
                log(f"Validating row {row_num}...")
                errors = validate_row(ws, row_num)
                if errors:
                    for err in errors:
                        log(f"  VALIDATION ERROR: {err}")
                    writer.write_status(row_num, f"VALIDATION FAILED: {'; '.join(errors)}")
                    fail_count += 1
                    continue

                # ── Read Row Data ──
                row_data = read_claim_row(ws, row_num)
                loan_app_no = row_data["loan_app_no"]
                log(f"Loan Application No: {loan_app_no}")

                check()

                # ── Search for Loan Application ──
                search_loan_application(page, loan_app_no, log_callback=log)
                check()

                # ── Click ADD ──
                click_add_button(page, log_callback=log)
                check()

                # ── Fill Claim Form ──
                fill_claim_form(page, row_data, profile, log_callback=log)
                check()

                # ── SAVE & CONTINUE ──
                save_and_continue(page, log_callback=log)
                check()

                # ── SUBMIT ──
                submit_claim(page, log_callback=log)
                check()

                # ── Extract Claim ID ──
                claim_id = extract_claim_id(page, log_callback=log)

                # ── Write Claim ID to Excel ──
                writer.write_claim_id(row_num, claim_id)
                log(f"Row {row_num} COMPLETED — Claim ID: {claim_id}")
                success_count += 1

                # ── Cleanup for next row (multi mode) ──
                if mode == "multi" and row_num < end_row - 1:
                    _reset_page_for_next_row(page, log)
                    # Re-apply filters for the next search
                    select_filters_and_proceed(page, profile, log_callback=log)
                    check()

            except AutomationStoppedError:
                log(f"Row {row_num} interrupted by STOP.")
                raise

            except Exception as e:
                error_msg = str(e)
                log(f"ERROR on Row {row_num}: {error_msg}")
                log_error(f"Row {row_num}: {error_msg}")

                try:
                    screenshot_name = f"error_row{row_num}_{datetime.now().strftime('%H%M%S')}.png"
                    take_screenshot(page, screenshot_name)
                    log(f"Screenshot saved: {screenshot_name}")
                except Exception:
                    pass

                try:
                    writer.write_status(row_num, f"ERROR: {error_msg[:100]}")
                except Exception:
                    pass

                fail_count += 1

                if mode == "single":
                    break
                else:
                    _reset_page_for_next_row(page, log)
                    # Re-apply filters after error recovery
                    try:
                        select_filters_and_proceed(page, profile, log_callback=log)
                    except Exception:
                        pass
                    continue

        # ── Summary ──
        log(f"{'═' * 50}")
        log(f"AUTOMATION COMPLETE")
        log(f"  Successful: {success_count}")
        log(f"  Failed: {fail_count}")
        log(f"  Stopped: {'Yes' if stop_event.is_set() else 'No'}")
        log(f"{'═' * 50}")

    except AutomationStoppedError:
        log("Automation STOPPED by user.")

    except Exception as e:
        log(f"FATAL ERROR: {str(e)}")
        log_error(f"Fatal: {str(e)}")
        try:
            take_screenshot(page, f"fatal_{datetime.now().strftime('%H%M%S')}.png")
        except Exception:
            pass

    finally:
        # Flush & close the Excel write session
        if writer:
            try:
                writer.close()
                log("Excel saved")
            except Exception:
                pass

        # Clear browser references
        browser_ref.pop("browser", None)
        browser_ref.pop("p", None)
        if p and browser:
            log("Closing browser...")
            close_browser(p, browser)
            log("Browser closed")
