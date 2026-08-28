from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from backend.app.models import RecoveryCase, PolicySettings, RecoveryAction, AuditEvent
from backend.app.config import settings

def get_current_policy(db: Session) -> PolicySettings:
    """
    Fetches the active policy settings. Creates default settings if none exists.
    """
    policy = db.query(PolicySettings).order_by(PolicySettings.id.desc()).first()
    if not policy:
        policy = PolicySettings(
            max_retries=settings.MAX_RETRY_ATTEMPTS,
            retry_cooldown=settings.DAILY_ACTION_LIMIT,  # placeholder
            auto_recovery_ceiling=settings.MAX_AUTOMATIC_RECOVERY_AMOUNT,
            human_approval_threshold=settings.MAX_AUTOMATIC_RECOVERY_AMOUNT,
            daily_action_limit=settings.DAILY_ACTION_LIMIT,
            comms_enabled=True,
            hinglish_enabled=True
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
    return policy

def validate_action_guardrails(db: Session, case: RecoveryCase, action_type: str, confidence: float, decision_source: str) -> tuple[bool, str, str]:
    """
    Checks if the recommended recovery action violates any deterministic guardrail policy.
    Returns (is_allowed, action_state_override, reason).
    
    If is_allowed is False, action_state_override dictates whether it is BLOCKED or ESCALATED.
    """
    payment = case.payment
    customer = payment.customer
    policy = get_current_policy(db)
    
    # 1. Unsupported action validation
    allowed_actions = {
        "retry_payment", "schedule_retry", "send_payment_reminder",
        "request_payment_method_update", "request_mandate_reauthorization",
        "escalate_to_human", "no_action"
    }
    if action_type not in allowed_actions:
        return False, "BLOCKED", f"Unsupported recovery action: {action_type}"
        
    # Automatically escalate to human review status if recommended
    if action_type == "escalate_to_human":
        return False, "ESCALATED", "Recommended action is escalate to human."
        
    # 2. Refund protection policy
    if customer.previous_refund_requested:
        if action_type in ["retry_payment", "schedule_retry", "send_payment_reminder", "request_payment_method_update", "request_mandate_reauthorization"]:
            return False, "BLOCKED", "Refund was previously requested by customer. Blocking recovery to prevent double-charging or customer dispute."
            
    # 3. Communication opt-out policy
    if customer.opted_out_of_comms or not policy.comms_enabled:
        if action_type in ["send_payment_reminder", "request_payment_method_update", "request_mandate_reauthorization"]:
            return False, "BLOCKED", "Customer has opted out of communication or global comms are disabled. Blocking communication action."
            
    # 4. Maximum retries policy
    # Check retry count in case (how many retries RecoverAI has attempted) plus retry_count_so_far from payment gateway
    total_retries = case.retry_count + payment.retry_count_so_far
    if action_type in ["retry_payment", "schedule_retry"] and total_retries >= policy.max_retries:
        return False, "ESCALATED", f"Retry limit reached ({total_retries} attempts). Escolating to human operator."

    # 5. High-value transaction policy
    if payment.amount > policy.auto_recovery_ceiling:
        if action_type in ["retry_payment", "schedule_retry"]:
            return False, "ESCALATED", f"High-value transaction (Amount ₹{payment.amount:.2f} > ₹{policy.auto_recovery_ceiling:.2f}). Requires human approval."
            
    # 6. AI Confidence threshold policy
    if decision_source == "ai" and confidence < settings.MIN_AI_CONFIDENCE:
        return False, "ESCALATED", f"AI confidence ({confidence:.2f}) is below safety threshold ({settings.MIN_AI_CONFIDENCE:.2f}). Escalating to human."

    # 7. Daily action limit policy
    # Count automated executions within the last 24 hours
    twenty_four_hours_ago = datetime.utcnow() - timedelta(days=1)
    daily_executions = db.query(RecoveryAction).filter(
        RecoveryAction.executed_at >= twenty_four_hours_ago,
        RecoveryAction.status == "SUCCESS",
        RecoveryAction.action_type.in_(["retry_payment", "schedule_retry"])
    ).count()
    
    if daily_executions >= policy.daily_action_limit:
        return False, "ESCALATED", f"Daily automatic action limit reached ({daily_executions} actions). Escalated to prevent runaways."
        
    return True, "APPROVED", "All guardrails passed successfully."
