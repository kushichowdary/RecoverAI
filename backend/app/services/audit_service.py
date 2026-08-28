from sqlalchemy.orm import Session
from backend.app.models import AuditEvent
from datetime import datetime

def log_audit_event(
    db: Session,
    action: str,
    record_id: str = None,
    customer_id: str = None,
    case_id: str = None,
    actor: str = "system",
    decision_source: str = None,
    reason: str = None,
    policy_result: str = None,
    idempotency_key: str = None,
    provider_result: str = None,
    outcome: str = None
) -> AuditEvent:
    event = AuditEvent(
        timestamp=datetime.utcnow(),
        record_id=record_id,
        customer_id=customer_id,
        case_id=case_id,
        action=action,
        actor=actor,
        decision_source=decision_source,
        reason=reason,
        policy_result=policy_result,
        idempotency_key=idempotency_key,
        provider_result=provider_result,
        outcome=outcome
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
