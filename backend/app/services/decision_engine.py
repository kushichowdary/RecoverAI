import json
from sqlalchemy.orm import Session
from backend.app.models import PaymentRecord, Customer, AIDecision, RecoveryCase
from backend.app.services.classifier import classify_failure_deterministically
from backend.app.ai.ai_provider import get_ai_provider

def determine_recovery_action(db: Session, case: RecoveryCase) -> tuple[str, float, str, str]:
    """
    Orchestrates the decision of the recommended recovery action.
    Returns (recommended_action, confidence, decision_source, reason).
    """
    payment = case.payment
    customer = payment.customer
    
    # 1. Deterministic check first
    action, confidence, is_ambiguous = classify_failure_deterministically(payment.failure_code)
    
    if not is_ambiguous:
        return action, confidence, "rules", f"Deterministic classification rule matched for failure '{payment.failure_code}'."
        
    # 2. Ambiguous failure, use AI Provider
    ai_provider = get_ai_provider()
    
    payment_info = {
        "record_id": payment.record_id,
        "customer_id": payment.customer_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "failure_code": payment.failure_code,
        "retry_count_so_far": payment.retry_count_so_far,
        "payment_method": payment.payment_method,
        "days_since_failure": payment.days_since_failure,
        "previous_success_count": customer.previous_success_count,
        "previous_failure_count": customer.previous_failure_count,
        "previous_refund_requested": customer.previous_refund_requested,
        "opted_out_of_comms": customer.opted_out_of_comms
    }
    
    # Get recommendation from AI with safe fallback if it fails/outages or returns malformed data
    try:
        ai_recommendation = ai_provider.recommend_recovery(payment_info)
        if not ai_recommendation:
            raise ValueError("AI returned empty recommendation.")
            
        # Log to AIDecision
        ai_decision = AIDecision(
            case_id=case.case_id,
            prompt=f"Payment Context: {json.dumps(payment_info)}",
            raw_response=json.dumps(ai_recommendation.model_dump()),
            classification=ai_recommendation.classification,
            recommended_action=ai_recommendation.recommended_action,
            confidence=ai_recommendation.confidence,
            reason=ai_recommendation.reason
        )
        db.add(ai_decision)
        db.commit()
        
        return (
            ai_recommendation.recommended_action,
            ai_recommendation.confidence,
            "ai",
            ai_recommendation.reason
        )
    except Exception as e:
        # Outage fallback: escalate to human review for ambiguous failure codes
        # We do NOT run default recovery attempts automatically if AI fails on ambiguous records
        return (
            "escalate_to_human",
            1.0,
            "rules",
            f"AI unavailable or returned malformed output ({str(e)}). Ambiguous failure '{payment.failure_code}' escalated for safety."
        )
