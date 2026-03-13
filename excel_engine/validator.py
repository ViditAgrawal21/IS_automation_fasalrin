"""
Excel validator for IS Claim data.

Validates that mandatory columns have values before attempting automation.
"""

import re
from utils.constants import ClaimCol


# Human-readable column names for error messages
_COL_NAMES = {
    ClaimCol.LOAN_APP_NO: "Loan Application No (col B)",
    ClaimCol.FIRST_DISBURSAL_DATE: "First Loan Disbursal Date (col C)",
    ClaimCol.ROLLOVER_DATE: "Loan Repayment/Rollover Date (col D)",
    ClaimCol.MAX_WITHDRAWAL: "Max Withdrawal Amount (col E)",
    ClaimCol.APPLICABLE_IS: "Applicable PRI/IS (col F)",
}


def _is_valid_loan_app_no(val) -> tuple:
    """
    Validate Loan Application Number — must be a proper number (digits only).

    Returns:
        (is_valid: bool, error_msg: str or None)
    """
    if val is None:
        return False, "Loan Application No is empty"

    # If it's a number type from Excel, check it's a whole number
    if isinstance(val, (int, float)):
        if isinstance(val, float) and val != int(val):
            return False, f"Application number not proper — got decimal value '{val}'"
        return True, None

    # String — must be digits only (after stripping whitespace)
    s = str(val).strip()
    if not s:
        return False, "Loan Application No is empty"

    # Remove trailing .0 that Excel sometimes adds
    if s.endswith(".0"):
        s = s[:-2]

    if not re.match(r'^\d+$', s):
        return False, f"Application number not proper — '{val}' is not a valid number"

    return True, None


def validate_row(ws, row: int) -> list:
    """
    Validate a single row for mandatory fields.

    Args:
        ws: Sheet1 worksheet.
        row: 1-based row number.

    Returns:
        List of error strings. Empty list means valid.
    """
    errors = []

    # Validate Loan Application Number specifically
    loan_val = ws.cell(row=row, column=ClaimCol.LOAN_APP_NO).value
    is_valid, err_msg = _is_valid_loan_app_no(loan_val)
    if not is_valid:
        errors.append(err_msg)

    # Validate other mandatory fields (skip LOAN_APP_NO as already checked)
    for col_idx in ClaimCol.MANDATORY:
        if col_idx == ClaimCol.LOAN_APP_NO:
            continue
        val = ws.cell(row=row, column=col_idx).value
        if val is None or str(val).strip() == "":
            col_name = _COL_NAMES.get(col_idx, f"Column {col_idx}")
            errors.append(f"Missing: {col_name}")

    return errors
