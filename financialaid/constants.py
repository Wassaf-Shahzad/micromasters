"""
Constants for financialaid
"""
from urllib.parse import quote_plus

from django.conf import settings


class FinancialAidJustification:
    """
    Justifications for financial aid decisions
    """
    OKAY = "Documents in order"
    NOT_NOTARIZED = "Docs not notarized"
    INSUFFICIENT = "Insufficient docs"
    INCOME_INACCURATE = "Inaccurate income reported"
    COUNTRY_INACCURATE = "Inaccurate country reported"

    ALL_JUSTIFICATIONS = [OKAY, NOT_NOTARIZED, INSUFFICIENT, INCOME_INACCURATE, COUNTRY_INACCURATE]


class FinancialAidStatus:
    """Statuses for the Financial Aid model"""
    APPROVED = 'approved'
    AUTO_APPROVED = 'auto-approved'
    CREATED = 'created'
    DOCS_SENT = 'docs-sent'
    PENDING_DOCS = 'pending-docs'
    PENDING_MANUAL_APPROVAL = 'pending-manual-approval'
    SKIPPED = 'skipped'

    ALL_STATUSES = [
        APPROVED,
        AUTO_APPROVED,
        CREATED,
        DOCS_SENT,
        PENDING_DOCS,
        PENDING_MANUAL_APPROVAL,
        SKIPPED
    ]
    TERMINAL_STATUSES = [APPROVED, AUTO_APPROVED, SKIPPED]

    STATUS_MESSAGES_DICT = {
        APPROVED: "Approved",
        AUTO_APPROVED: "Auto-Approved",
        CREATED: "--",
        DOCS_SENT: "Documents Sent by User",
        PENDING_DOCS: "Started Applications",
        PENDING_MANUAL_APPROVAL: "Pending Approval (Documents Received)",
        SKIPPED: "Skipped"
    }


CURRENCY_EXCHANGE_RATE_API_REQUEST_URL = "{url}latest.json?app_id={app_id}".format(
    url=settings.OPEN_EXCHANGE_RATES_URL,
    app_id=quote_plus(settings.OPEN_EXCHANGE_RATES_APP_ID)
)

FINANCIAL_AID_DOCUMENTS_RECEIVED_SUBJECT = "Documents received for {program_name} MicroMasters"
FINANCIAL_AID_APPROVAL_SUBJECT = "Your personalized course price for {program_name} MicroMasters"

FINANCIAL_AID_EMAIL_BODY = (
    "Dear {first_name},\n\n"
    "{message}\n\n"
    "Thank you,\n"
    "The {program_name} MicroMasters team"
)

FINANCIAL_AID_DOCUMENTS_RECEIVED_MESSAGE = (
    "We have received your documents verifying your income. We will review them as soon as possible, "
    "after which we will send an e-mail confirming your personalized course price. We encourage you "
    "to enroll now and pay later, when a decision has been reached."
)
FINANCIAL_AID_APPROVAL_MESSAGE = (
    "After reviewing your income documentation, the {program_name} MicroMasters team has determined "
    "that your personalized course price is ${price}.\n\n"
    "You can pay for MicroMasters courses through the MIT MicroMasters portal "
    "(https://micromasters.mit.edu/dashboard). All coursework will be conducted on edx.org."
)

DEFAULT_INCOME_THRESHOLD = 75000
COUNTRY_INCOME_THRESHOLDS = {
    "AD": 75000,
    "AG": 75000,
    "AW": 75000,
    "AU": 75000,
    "AT": 75000,
    "BS": 75000,
    "BH": 75000,
    "BB": 75000,
    "BE": 75000,
    "BM": 75000,
    "VG": 75000,
    "BN": 75000,
    "CA": 75000,
    "KY": 75000,
    "CL": 75000,
    "HR": 75000,
    "CW": 75000,
    "CY": 75000,
    "CZ": 75000,
    "DK": 75000,
    "EE": 75000,
    "FO": 75000,
    "FI": 75000,
    "FR": 75000,
    "PF": 75000,
    "DE": 75000,
    "GI": 75000,
    "GR": 75000,
    "GL": 75000,
    "GU": 75000,
    "HK": 75000,
    "HU": 75000,
    "IS": 75000,
    "IE": 75000,
    "IM": 75000,
    "IL": 75000,
    "IT": 75000,
    "JP": 75000,
    "KR": 75000,
    "KW": 75000,
    "LV": 75000,
    "LI": 75000,
    "LT": 75000,
    "LU": 75000,
    "MO": 75000,
    "MT": 75000,
    "MC": 75000,
    "NR": 75000,
    "NL": 75000,
    "NC": 75000,
    "NZ": 75000,
    "MP": 75000,
    "NO": 75000,
    "OM": 75000,
    "PL": 75000,
    "PT": 75000,
    "PR": 75000,
    "QA": 75000,
    "SM": 75000,
    "SA": 75000,
    "SC": 75000,
    "SG": 75000,
    "SX": 75000,
    "SK": 75000,
    "SI": 75000,
    "ES": 75000,
    "KN": 75000,
    "MF": 75000,
    "SE": 75000,
    "CH": 75000,
    "TW": 75000,
    "TT": 75000,
    "TC": 75000,
    "AE": 75000,
    "GB": 75000,
    "US": 75000,
    "UY": 75000,
    "VI": 75000,
    "AL": 50000,
    "DZ": 50000,
    "AS": 50000,
    "AO": 50000,
    "AZ": 50000,
    "BY": 50000,
    "BZ": 50000,
    "BA": 50000,
    "BW": 50000,
    "BR": 50000,
    "BG": 50000,
    "CN": 50000,
    "CO": 50000,
    "CR": 50000,
    "CU": 50000,
    "DM": 50000,
    "DO": 50000,
    "EC": 50000,
    "GQ": 50000,
    "FJ": 50000,
    "GA": 50000,
    "GE": 50000,
    "GD": 50000,
    "GY": 50000,
    "IR": 50000,
    "IQ": 50000,
    "JM": 50000,
    "JO": 50000,
    "KZ": 50000,
    "LB": 50000,
    "LY": 50000,
    "MK": 50000,
    "MY": 50000,
    "MV": 50000,
    "MH": 50000,
    "MU": 50000,
    "MX": 50000,
    "ME": 50000,
    "NA": 50000,
    "PW": 50000,
    "PA": 50000,
    "PY": 50000,
    "PE": 50000,
    "RO": 50000,
    "RU": 50000,
    "RS": 50000,
    "ZA": 50000,
    "LC": 50000,
    "VC": 50000,
    "SR": 50000,
    "TH": 50000,
    "TR": 50000,
    "TM": 50000,
    "TV": 50000,
    "VE": 50000,
    "AM": 25000,
    "BD": 25000,
    "BT": 25000,
    "BO": 25000,
    "CV": 25000,
    "KH": 25000,
    "CM": 25000,
    "CG": 25000,
    "CI": 25000,
    "DJ": 25000,
    "EG": 25000,
    "SV": 25000,
    "GH": 25000,
    "GT": 25000,
    "HN": 25000,
    "IN": 25000,
    "ID": 25000,
    "KE": 25000,
    "KI": 25000,
    "XK": 25000,
    "KG": 25000,
    "LA": 25000,
    "LS": 25000,
    "MR": 25000,
    "FM": 25000,
    "MD": 25000,
    "MN": 25000,
    "MA": 25000,
    "MM": 25000,
    "NI": 25000,
    "NG": 25000,
    "PK": 25000,
    "PG": 25000,
    "PH": 25000,
    "WS": 25000,
    "ST": 25000,
    "SB": 25000,
    "LK": 25000,
    "SD": 25000,
    "SZ": 25000,
    "SY": 25000,
    "TJ": 25000,
    "TL": 25000,
    "TO": 25000,
    "TN": 25000,
    "UA": 25000,
    "UZ": 25000,
    "VU": 25000,
    "VN": 25000,
    "PS": 25000,
    "YE": 25000,
    "ZM": 25000,
    "AF": 0,
    "BJ": 0,
    "BF": 0,
    "BI": 0,
    "CF": 0,
    "TD": 0,
    "KM": 0,
    "CD": 0,
    "ER": 0,
    "ET": 0,
    "GM": 0,
    "GN": 0,
    "GW": 0,
    "HT": 0,
    "KP": 0,
    "LR": 0,
    "MG": 0,
    "MW": 0,
    "ML": 0,
    "MZ": 0,
    "NP": 0,
    "NE": 0,
    "RW": 0,
    "SN": 0,
    "SL": 0,
    "SO": 0,
    "SS": 0,
    "TZ": 0,
    "TG": 0,
    "UG": 0,
    "ZW": 0
}
