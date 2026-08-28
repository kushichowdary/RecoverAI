from sqlalchemy.orm import Session
from backend.app.models import PaymentRecord, RecoveryCase
from datetime import datetime, timedelta

def check_duplicate_payment(db: Session, payment: PaymentRecord) -> tuple[bool, str]:
    """
    Checks if there is an existing payment failure within 5 minutes 
    for the same customer, order, and amount.
    Returns (is_duplicate, reason).
    """
    # Exclude the current record itself from the check
    five_minutes_ago = payment.failure_timestamp - timedelta(minutes=5)
    
    # Query for potentially duplicate payments in the 5-minute window
    duplicate = db.query(PaymentRecord).filter(
        PaymentRecord.record_id != payment.record_id,
        PaymentRecord.customer_id == payment.customer_id,
        PaymentRecord.order_id == payment.order_id,
        PaymentRecord.amount == payment.amount,
        PaymentRecord.failure_timestamp >= five_minutes_ago,
        PaymentRecord.failure_timestamp <= payment.failure_timestamp
    ).order_by(PaymentRecord.failure_timestamp.asc()).first()
    
    if duplicate:
        # Check if the duplicate already has an active or completed recovery case
        existing_case = db.query(RecoveryCase).filter(
            RecoveryCase.payment_record_id == duplicate.record_id
        ).first()
        
        if existing_case:
            return True, f"Duplicate of payment {duplicate.record_id} which has recovery case {existing_case.case_id}"
        return True, f"Duplicate of payment {duplicate.record_id}"
        
    return False, ""
