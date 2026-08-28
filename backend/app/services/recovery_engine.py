import logging
from sqlalchemy.orm import Session
from backend.app.models import PaymentRecord, RecoveryCase
from backend.app.services.deduplication import check_duplicate_payment
from backend.app.services.decision_engine import determine_recovery_action
from backend.app.services.guardrails import validate_action_guardrails, get_current_policy
from backend.app.services.audit_service import log_audit_event
from datetime import datetime

logger = logging.getLogger("recoverai")

def transition_case_status(db: Session, case: RecoveryCase, new_status: str, reason: str = None) -> None:
    """
    Transitions the recovery case status while validating against strict state-machine rules.
    """
    current_status = case.status
    if current_status == new_status:
        return
        
    ALLOWED_TRANSITIONS = {
        "DETECTED": {"ANALYZING", "BLOCKED", "ESCALATED"},
        "ANALYZING": {"DECIDED", "ESCALATED", "FAILED"},
        "DECIDED": {"GUARDRAIL_CHECK", "ESCALATED", "FAILED"},
        "GUARDRAIL_CHECK": {"APPROVED", "BLOCKED", "ESCALATED"},
        "APPROVED": {"EXECUTING", "ESCALATED", "RECOVERED"},
        "EXECUTING": {"VERIFYING", "FAILED", "RETRY_PENDING", "ESCALATED", "RECOVERED", "STATE_UNKNOWN"},
        "VERIFYING": {"RECOVERED", "FAILED", "STATE_UNKNOWN", "ESCALATED"},
        "RECOVERED": set(),
        "BLOCKED": set(),
        "FAILED": {"EXECUTING", "ESCALATED", "RETRY_PENDING"},
        "RETRY_PENDING": {"EXECUTING", "ESCALATED", "APPROVED"},
        "ESCALATED": {"APPROVED", "EXECUTING", "RECOVERED", "FAILED"},
        "STATE_UNKNOWN": {"VERIFYING", "ESCALATED", "RECOVERED", "FAILED"}
    }
    
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ValueError(f"Invalid state transition: Cannot transition Recovery Case status from '{current_status}' to '{new_status}'.")
        
    case.status = new_status
    if new_status == "BLOCKED" and reason:
        case.block_reason = reason
    elif new_status == "ESCALATED" and reason:
        case.escalation_reason = reason
    db.commit()

def ingest_failed_payment(db: Session, payment_record_id: str) -> RecoveryCase:
    """
    Ingests a failed payment, creates a recovery case, and runs the classification and safety checks.
    """
    payment = db.query(PaymentRecord).filter(PaymentRecord.record_id == payment_record_id).first()
    if not payment:
        raise ValueError(f"Payment record {payment_record_id} not found.")

    # Check if case already exists
    existing_case = db.query(RecoveryCase).filter(
        RecoveryCase.payment_record_id == payment_record_id
    ).first()
    if existing_case:
        return existing_case

    # 1. State: DETECTED
    case = RecoveryCase(
        payment_record_id=payment_record_id,
        status="DETECTED",
        created_at=datetime.utcnow()
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    
    log_audit_event(
        db, action="payment_failure_detected", record_id=payment.record_id,
        customer_id=payment.customer_id, case_id=case.case_id,
        reason=f"Payment failure ingested: {payment.failure_code}"
    )

    # 2. Deduplication check
    is_duplicate, dup_reason = check_duplicate_payment(db, payment)
    if is_duplicate:
        transition_case_status(db, case, "BLOCKED", dup_reason)
        
        log_audit_event(
            db, action="deduplication_failed", record_id=payment.record_id,
            customer_id=payment.customer_id, case_id=case.case_id,
            reason=dup_reason, policy_result="BLOCKED"
        )
        return case

    # 3. State: ANALYZING -> DECIDED
    transition_case_status(db, case, "ANALYZING")
    
    recommended_action, confidence, source, explanation = determine_recovery_action(db, case)
    
    case.recommended_action = recommended_action
    case.recovery_probability = confidence
    case.decision_source = source
    transition_case_status(db, case, "DECIDED")
    
    log_audit_event(
        db, action="recovery_decision_made", record_id=payment.record_id,
        customer_id=payment.customer_id, case_id=case.case_id,
        decision_source=source, reason=explanation, outcome=recommended_action
    )

    # 4. State: GUARDRAIL_CHECK -> APPROVED/BLOCKED/ESCALATED
    transition_case_status(db, case, "GUARDRAIL_CHECK")
    
    allowed, override_state, guardrail_reason = validate_action_guardrails(
        db, case, recommended_action, confidence, source
    )
    
    if not allowed:
        if override_state == "BLOCKED":
            transition_case_status(db, case, "BLOCKED", guardrail_reason)
        else:
            transition_case_status(db, case, "ESCALATED", guardrail_reason)
            
        log_audit_event(
            db, action="guardrail_blocked" if override_state == "BLOCKED" else "guardrail_escalated",
            record_id=payment.record_id, customer_id=payment.customer_id, case_id=case.case_id,
            reason=guardrail_reason, policy_result=override_state
        )
        return case

    # Guardrails passed -> APPROVED
    transition_case_status(db, case, "APPROVED")
    
    log_audit_event(
        db, action="guardrails_passed", record_id=payment.record_id,
        customer_id=payment.customer_id, case_id=case.case_id,
        policy_result="APPROVED"
    )

    # 5. Check if we should automatically execute
    # Auto-execute if recommended action is an automatic action and payment is within auto-recovery limit
    policy = get_current_policy(db)
    is_auto_action = recommended_action in ["retry_payment", "schedule_retry", "send_payment_reminder", "request_payment_method_update", "request_mandate_reauthorization"]
    
    # Auto recover ceiling is applied for payment retries
    is_retry = recommended_action in ["retry_payment", "schedule_retry"]
    under_ceiling = payment.amount <= policy.auto_recovery_ceiling
    
    # Only auto execute retries if under ceiling, other actions like reminders can be auto-executed if comms enabled
    should_auto_execute = False
    if is_retry and under_ceiling:
        should_auto_execute = True
    elif is_auto_action and not is_retry:
        should_auto_execute = True

    if should_auto_execute:
        logger.info(f"Auto-executing recovery action {recommended_action} for case {case.case_id}")
        from backend.app.services.executor import execute_recovery_action
        execute_recovery_action(db, case.case_id)
        
    return case
