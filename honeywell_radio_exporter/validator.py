"""
Validate normalized RAMSES messages. Extend rules against ramses_protocol.
Unknown codes: ok=False with errors logged by caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str]
    code_name: Optional[str] = None


def validate_message(
    *,
    code: str,
    verb: str,
    payload: Any,
    code_name_hint: Optional[str] = None,
) -> ValidationResult:
    """
    Lightweight validation: non-empty code/verb; optional payload shape checks later.
    """
    _ = payload
    errors: List[str] = []
    if not code or code == "unknown":
        errors.append("missing code")
    if not verb or verb == "unknown":
        errors.append("missing verb")
    ok = len(errors) == 0
    return ValidationResult(ok=ok, errors=errors, code_name=code_name_hint)
