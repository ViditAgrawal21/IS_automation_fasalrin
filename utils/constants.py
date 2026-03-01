"""
Constants for the IS Claim Automation system.

Contains:
  - Portal URLs
  - Excel column mappings (ClaimCol)
  - Dropdown values for profile & form fields
"""

# ═══════════════════════════════════════════════════════════════
# Portal URLs
# ═══════════════════════════════════════════════════════════════

LOGIN_URL = "https://fasalrin.gov.in/login"
CLAIM_LIST_URL = "https://fasalrin.gov.in/claim-application-list"
DASHBOARD_URL = "https://fasalrin.gov.in/dashboard"
WELCOME_URL = "https://fasalrin.gov.in/welcome"


# ═══════════════════════════════════════════════════════════════
# Excel Column Mapping — Sheet1
# ═══════════════════════════════════════════════════════════════
# Column indices are 1-based (openpyxl convention).
#
# A(1)  = #SR
# B(2)  = Loan Application No
# C(3)  = First Loan Disbursal Date
# D(4)  = Loan Repayment / Rollover Date
# E(5)  = Max Withdrawal Amount (INR)
# F(6)  = Applicable PRI/IS (INR)
# G(7)  = Claim ID              ← OUTPUT
# H(8)  = Season
# I(9)  = Account Number
# ═══════════════════════════════════════════════════════════════

class ClaimCol:
    """Column indices for the IS Claim Excel sheet (1-based)."""
    SR = 1                          # A — Serial number
    LOAN_APP_NO = 2                 # B — Loan Application No
    FIRST_DISBURSAL_DATE = 3        # C — First Loan Disbursal Date
    ROLLOVER_DATE = 4               # D — Loan Repayment / Rollover Date
    MAX_WITHDRAWAL = 5              # E — Max Withdrawal Amount (INR)
    APPLICABLE_IS = 6               # F — Applicable PRI/IS (INR)
    CLAIM_ID = 7                    # G — Claim ID (output)
    SEASON = 8                      # H — Season
    ACCOUNT_NUMBER = 9              # I — Account Number

    # Mandatory columns that must have values for automation
    MANDATORY = [LOAN_APP_NO, FIRST_DISBURSAL_DATE, ROLLOVER_DATE,
                 MAX_WITHDRAWAL, APPLICABLE_IS]


# ═══════════════════════════════════════════════════════════════
# Dropdown Values — Financial Year
# ═══════════════════════════════════════════════════════════════

FINANCIAL_YEARS = [
    "2022-2023",
    "2023-2024",
    "2024-2025",
    "2025-2026",
    "2026-2027",
]


# ═══════════════════════════════════════════════════════════════
# Dropdown Values — Claim Type
# ═══════════════════════════════════════════════════════════════

CLAIM_TYPES = [
    "IS",     # value="1"
    "PRI",    # value="2"
]

# Map display name → portal <option> value
CLAIM_TYPE_VALUES = {
    "IS": "1",
    "PRI": "2",
}


# ═══════════════════════════════════════════════════════════════
# Dropdown Values — Claim Status
# ═══════════════════════════════════════════════════════════════

CLAIM_STATUSES = [
    "PENDING",     # value="-1"
    "DRAFT",       # value="0"
    "SUBMITTED",   # value="1"
    "APPROVED",    # value="2"
    "REJECTED",    # value="3"
    "ROLLOVER",    # value="6"
]

CLAIM_STATUS_VALUES = {
    "PENDING": "-1",
    "DRAFT": "0",
    "SUBMITTED": "1",
    "APPROVED": "2",
    "REJECTED": "3",
    "ROLLOVER": "6",
}


# ═══════════════════════════════════════════════════════════════
# Dropdown Values — IS Submission Type
# ═══════════════════════════════════════════════════════════════

SUBMISSION_TYPES = [
    "COMPLETE",    # value="1"
    "PARTIAL",     # value="2"
]

SUBMISSION_TYPE_VALUES = {
    "COMPLETE": "1",
    "PARTIAL": "2",
}
