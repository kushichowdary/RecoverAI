from sqlalchemy.orm import Session
from backend.app.models import PaymentRecord, RecoveryCase
from backend.app.integrations.payment_adapter import get_payment_adapter
from backend.app.services.audit_service import log_audit_event

def verify_payment_status(db: Session, case_id: str) -> dict:
    """
    Verifies the payment state on the gateway and synchronizes the recovery case state.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.case_id == case_id).first()
    if not case:
        return {"status": "failed", "detail": "Case not found."}
        
    payment = case.payment
    customer = payment.customer
    
    case.status = "VERIFYING"
    db.commit()
    
    adapter = get_payment_adapter()
    try:
        resp = adapter.verify_payment(payment.record_id)
        gateway_status = resp.get("status")
        
        if gateway_status == "captured":
            payment.status = "RECOVERED"
            case.status = "RECOVERED"
            outcome = "recovered"
        elif gateway_status == "failed":
            payment.status = "FAILED"
            case.status = "FAILED"
            outcome = "still_failed"
        else:
            case.status = "STATE_UNKNOWN"
            case.escalation_reason = f"Gateway verification returned status '{gateway_status}'."
            outcome = "escalated"
            
        db.commit()
        
        log_audit_event(
            db, action="payment_verified", record_id=payment.record_id,
            customer_id=customer.customer_id, case_id=case.case_id,
            provider_result=f"Verified status: {gateway_status}", outcome=outcome
        )
        return {"status": outcome, "gateway_status": gateway_status}
        
    except Exception as e:
        case.status = "STATE_UNKNOWN"
        case.escalation_reason = f"Verification request failed: {str(e)}"
        db.commit()
        
        log_audit_event(
            db, action="payment_verified", record_id=payment.record_id,
            customer_id=customer.customer_id, case_id=case.case_id,
            provider_result=f"Verification failed: {str(e)}", outcome="escalated"
        )
        return {"status": "escalated", "detail": f"Verification failed: {str(e)}"}
