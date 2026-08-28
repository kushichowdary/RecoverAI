from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models import PaymentRecord, RecoveryCase, RecoveryAction

def calculate_dashboard_metrics(db: Session) -> dict:
    """
    Computes all essential dashboard metrics from the database.
    """
    # 1. Total revenue at risk (all payments currently in FAILED status)
    revenue_at_risk = db.query(func.sum(PaymentRecord.amount)).filter(
        PaymentRecord.status == "FAILED"
    ).scalar() or 0.0
    
    # 2. Revenue recovered (all payments in RECOVERED or SUCCESS status)
    revenue_recovered = db.query(func.sum(PaymentRecord.amount)).filter(
        PaymentRecord.status.in_(["RECOVERED", "SUCCESS"])
    ).scalar() or 0.0
    
    # 3. Recoverable revenue (all active cases that haven't finalized to recovered/failed/blocked/escalated)
    active_statuses = [
        "DETECTED", "ANALYZING", "DECIDED", "GUARDRAIL_CHECK", 
        "APPROVED", "EXECUTING", "VERIFYING", "RETRY_PENDING"
    ]
    recoverable_revenue = db.query(func.sum(PaymentRecord.amount)).join(
        RecoveryCase, PaymentRecord.record_id == RecoveryCase.payment_record_id
    ).filter(
        RecoveryCase.status.in_(active_statuses)
    ).scalar() or 0.0
    
    # Counts
    total_cases = db.query(RecoveryCase).count()
    successful_recoveries = db.query(RecoveryCase).filter(RecoveryCase.status == "RECOVERED").count()
    guardrail_blocks = db.query(RecoveryCase).filter(RecoveryCase.status == "BLOCKED").count()
    human_escalations = db.query(RecoveryCase).filter(RecoveryCase.status == "ESCALATED").count()
    failed_recoveries = db.query(RecoveryCase).filter(RecoveryCase.status == "FAILED").count()
    
    unresolved_statuses = ["BLOCKED", "FAILED", "ESCALATED", "STATE_UNKNOWN"]
    unresolved_cases = db.query(RecoveryCase).filter(RecoveryCase.status.in_(unresolved_statuses)).count()
    
    recovery_attempts = db.query(RecoveryAction).filter(
        RecoveryAction.action_type.in_(["retry_payment", "schedule_retry"])
    ).count()
    
    recovery_rate = (successful_recoveries / total_cases * 100.0) if total_cases > 0 else 0.0
    
    return {
        "revenue_at_risk": float(revenue_at_risk),
        "recoverable_revenue": float(recoverable_revenue),
        "revenue_recovered": float(revenue_recovered),
        "recovery_rate": round(recovery_rate, 2),
        "recovery_attempts": recovery_attempts,
        "successful_recoveries": successful_recoveries,
        "guardrail_blocks": guardrail_blocks,
        "human_escalations": human_escalations,
        "failed_recoveries": failed_recoveries,
        "unresolved_cases": unresolved_cases
    }
