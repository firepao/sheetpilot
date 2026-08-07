from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    INPUT_INVALID = "INPUT_INVALID"
    WORKBOOK_UNSUPPORTED = "WORKBOOK_UNSUPPORTED"
    SEMANTIC_AMBIGUITY = "SEMANTIC_AMBIGUITY"
    PLAN_INVALID = "PLAN_INVALID"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
    DYNAMIC_TRANSFORM_REJECTED = "DYNAMIC_TRANSFORM_REJECTED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    OUTPUT_CORRUPTED = "OUTPUT_CORRUPTED"
    VALIDATION_FAILED = "VALIDATION_FAILED"


class SheetPilotError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error": {"code": self.code.value, "message": self.message, "details": self.details}}
