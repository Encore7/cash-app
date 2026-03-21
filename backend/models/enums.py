from enum import StrEnum


class SourceType(StrEnum):
    BANK_STATEMENT = "bank_statement"
    REMITTANCE = "remittance"


class ScheduleFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class RunStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PARSED = "PARSED"
    MATCHED = "MATCHED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    READY_TO_POST = "READY_TO_POST"
    POSTED = "POSTED"
    FAILED = "FAILED"


class MatchStatus(StrEnum):
    AUTO_MATCHED = "AUTO_MATCHED"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    UNMATCHED = "UNMATCHED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"
