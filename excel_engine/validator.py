"""
Excel validator for IS Claim data.

Validates that mandatory columns have values before attempting automation.
"""

from utils.constants import ClaimCol


# Human-readable column names for error messages
_COL_NAMES = {
    ClaimCol.LOAN_APP_NO: "Loan Application No (col B)",
    ClaimCol.FIRST_DISBURSAL_DATE: "First Loan Disbursal Date (col C)",
    ClaimCol.ROLLOVER_DATE: "Loan Repayment/Rollover Date (col D)",
    ClaimCol.MAX_WITHDRAWAL: "Max Withdrawal Amount (col E)",
    ClaimCol.APPLICABLE_IS: "Applicable PRI/IS (col F)",
}


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

    for col_idx in ClaimCol.MANDATORY:
        val = ws.cell(row=row, column=col_idx).value
        if val is None or str(val).strip() == "":
            col_name = _COL_NAMES.get(col_idx, f"Column {col_idx}")
            errors.append(f"Missing: {col_name}")

    return errors
