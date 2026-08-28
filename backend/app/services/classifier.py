from typing import Optional, Tuple

# Deterministic mappings
DETERMINISTIC_ACTIONS = {
    "insufficient_funds": "retry_payment",
    "card_expired": "request_payment_method_update",
    "bank_timeout": "retry_payment",
    "network_error": "retry_payment",
    "mandate_revoked": "request_mandate_reauthorization"
}

def classify_failure_deterministically(failure_code: str) -> Tuple[Optional[str], Optional[float], bool]:
    """
    Returns (recommended_action, confidence, is_ambiguous).
    If is_ambiguous is True, it requires AI classification.
    """
    if not failure_code:
        return "escalate_to_human", 1.0, False
        
    code_lower = failure_code.lower()
    
    if code_lower in DETERMINISTIC_ACTIONS:
        # High confidence for deterministic rules
        return DETERMINISTIC_ACTIONS[code_lower], 1.0, False
        
    if code_lower in ["issuer_declined_generic", "do_not_honor"]:
        # Ambiguous failures require AI
        return None, None, True
        
    # Default fallback for unknown failure codes
    return None, None, True
