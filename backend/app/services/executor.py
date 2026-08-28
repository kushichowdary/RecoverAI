import json
import logging
from sqlalchemy.orm import Session
from backend.app.models import RecoveryCase, RecoveryAction, PaymentAttempt, Notification
from backend.app.integrations.payment_adapter import get_payment_adapter, RazorpayTestAdapter, MockRazorpayAdapter
from backend.app.services.audit_service import log_audit_event
from backend.app.services.guardrails import get_current_policy
from backend.app.ai.ai_provider import get_ai_provider
from backend.app.services.recovery_engine import transition_case_status
from datetime import datetime
import httpx

logger = logging.getLogger("recoverai")

def execute_recovery_action(db: Session, case_id: str, scenario_override: str = None, idempotency_key: str = None) -> dict:
    """
    Executes an approved recovery action for the given case.
    Handles idempotency, simulator overrides, and gateways.
    """
    case = db.query(RecoveryCase).filter(RecoveryCase.case_id == case_id).first()
    if not case:
        return {"outcome": "failed", "detail": "Case not found."}
        
    payment = case.payment
    customer = payment.customer
    
    # Calculate attempt number if not provided
    if not idempotency_key:
        attempt_num = db.query(RecoveryAction).filter(RecoveryAction.case_id == case.case_id).count() + 1
        idempotency_key = f"recovery:{payment.record_id}:{attempt_num}"
    
    # 1. Check if action with this idempotency key already exists
    existing_action = db.query(RecoveryAction).filter(
        RecoveryAction.idempotency_key == idempotency_key
    ).first()
    
    if existing_action:
        logger.info(f"[IDEMPOTENCY] Found existing execution for key: {idempotency_key}")
        try:
            saved_result = json.loads(existing_action.response_payload)
            outcome = saved_result.get("outcome", "duplicate")
            detail = saved_result.get("detail", f"Duplicate request blocked by idempotency key {idempotency_key}")
            saved_result["cached"] = True
        except Exception:
            outcome = "duplicate"
            if existing_action.status == "SUCCESS":
                outcome = "recovered"
            elif existing_action.status == "FAILED":
                outcome = "still_failed"
            detail = f"Duplicate request blocked by idempotency key {idempotency_key}"
            saved_result = {
                "outcome": outcome,
                "detail": detail,
                "cached": True
            }
            
        log_audit_event(
            db, action="execution_blocked", record_id=payment.record_id,
            customer_id=customer.customer_id, case_id=case.case_id,
            reason="Duplicate action detected via idempotency key.",
            idempotency_key=idempotency_key, outcome=outcome
        )
        return saved_result

    adapter = get_payment_adapter()

    # 2. Verify current payment state at the gateway to prevent duplicate captures/retries
    try:
        gateway_payment = adapter.fetch_payment(payment.record_id, db=db)
        if gateway_payment and gateway_payment.get("status") == "captured":
            payment.status = "RECOVERED"
            transition_case_status(db, case, "RECOVERED")
            log_audit_event(
                db, action="execution_skipped", record_id=payment.record_id,
                customer_id=customer.customer_id, case_id=case.case_id,
                reason="Pre-recovery gateway check: Payment is already captured.",
                outcome="already_completed"
            )
            return {"outcome": "already_completed", "detail": "Payment was already completed."}
    except Exception as e:
        logger.warning(f"Pre-recovery verification check failed to fetch payment from gateway: {e}")

    # Fallback to local DB state verification
    if payment.status in ["RECOVERED", "SUCCESS"]:
        transition_case_status(db, case, "RECOVERED")
        log_audit_event(
            db, action="execution_skipped", record_id=payment.record_id,
            customer_id=customer.customer_id, case_id=case.case_id,
            reason="Payment was already successfully completed in DB.",
            outcome="already_completed"
        )
        return {"outcome": "already_completed", "detail": "Payment was already completed."}

    action_type = case.recommended_action
    
    # Calculate attempt number
    attempt_num = db.query(RecoveryAction).filter(RecoveryAction.case_id == case.case_id).count() + 1
    
    # 3. Create RecoveryAction record
    action = RecoveryAction(
        case_id=case.case_id,
        action_type=action_type,
        status="EXECUTING",
        idempotency_key=idempotency_key,
        executed_at=datetime.utcnow()
    )
    db.add(action)
    db.commit()
    
    # Mark case state as EXECUTING
    transition_case_status(db, case, "EXECUTING")
    
    log_audit_event(
        db, action="execution_started", record_id=payment.record_id,
        customer_id=customer.customer_id, case_id=case.case_id,
        idempotency_key=idempotency_key
    )

    policy = get_current_policy(db)
    
    # Check if we should execute financial retry vs comms
    if action_type in ["retry_payment", "schedule_retry"]:
        try:
            # Create a PaymentAttempt entry
            attempt = PaymentAttempt(
                payment_record_id=payment.record_id,
                attempt_number=attempt_num,
                action_type=action_type,
                status="PENDING",
                timestamp=datetime.utcnow()
            )
            db.add(attempt)
            db.commit()

            if isinstance(adapter, RazorpayTestAdapter):
                # 1. Fetch current Razorpay status
                pay_details = adapter.fetch_payment(payment.record_id, db=db)
                status = pay_details.get("status")
                
                # 2. Verify state is authorized
                if status == "authorized":
                    # Verify amount/currency/order context
                    expected_paise = int(payment.amount * 100)
                    gateway_paise = pay_details.get("amount", 0)
                    if gateway_paise != expected_paise:
                        logger.warning(f"Amount mismatch for payment {payment.record_id}: Expected {expected_paise} paise, gateway has {gateway_paise} paise.")
                    
                    if pay_details.get("currency") != payment.currency:
                        logger.warning(f"Currency mismatch for payment {payment.record_id}: Expected {payment.currency}, gateway has {pay_details.get('currency')}.")
                        
                    if payment.order and pay_details.get("order_id") != payment.order.order_id:
                        logger.warning(f"Order context mismatch for payment {payment.record_id}: Expected {payment.order.order_id}, gateway has {pay_details.get('order_id')}.")
                    
                    # 3. Capture the payment
                    resp = adapter.capture_payment(payment.record_id, payment.amount)
                    
                    # 4. Verify resulting state
                    verified_details = adapter.fetch_payment(payment.record_id, db=db)
                    final_status = verified_details.get("status")
                elif status == "captured":
                    resp = pay_details
                    final_status = "captured"
                elif status == "not_found":
                    resp = {
                        "id": payment.record_id,
                        "status": "failed",
                        "error_code": "synthetic_payment_id",
                        "error_description": f"Payment ID '{payment.record_id}' is a local synthetic benchmark ID and does not exist on Razorpay live servers. Switch RAZORPAY_MODE=mock in Render environment settings to run simulated recoveries."
                    }
                    final_status = "failed"
                else:
                    # Never capture failed payments
                    resp = {
                        "id": payment.record_id,
                        "status": "failed",
                        "error_code": "payment_not_authorized",
                        "error_description": f"Direct capture of a failed/created payment is not supported by Razorpay REST API. Current status: {status}"
                    }
                    final_status = "failed"

            else:
                # MockRazorpayAdapter simulation retry
                resp = adapter.retry_payment(
                    payment_id=payment.record_id,
                    amount=payment.amount,
                    idempotency_key=idempotency_key,
                    scenario=scenario_override
                )
                final_status = resp.get("status")

            # Record execution outcome
            action.status = "SUCCESS" if final_status == "captured" else "FAILED"
            
            attempt.status = "SUCCESS" if final_status == "captured" else "FAILED"
            attempt.gateway_payment_id = resp.get("id")
            attempt.error_code = resp.get("error_code")
            attempt.error_description = resp.get("error_description")
            
            if final_status == "captured":
                payment.status = "RECOVERED"
                transition_case_status(db, case, "RECOVERED")
                outcome = "recovered"
                detail = "Execution finished with status captured"
            elif final_status == "unknown":
                payment.status = "FAILED"
                transition_case_status(db, case, "STATE_UNKNOWN", "Gateway returned unknown payment state.")
                outcome = "escalated"
                detail = "Execution finished with status unknown"
            else:
                # Still failed
                transition_case_status(db, case, "FAILED")
                payment.retry_count_so_far += 1
                case.retry_count += 1
                outcome = "still_failed"
                detail = resp.get("error_description") or f"Execution finished with status {final_status}"
                
            action.response_payload = json.dumps({
                "outcome": outcome,
                "detail": detail,
                "provider_result": resp
            })
            db.commit()
            
            log_audit_event(
                db, action="execution_completed", record_id=payment.record_id,
                customer_id=customer.customer_id, case_id=case.case_id,
                idempotency_key=idempotency_key, provider_result=json.dumps(resp),
                outcome=outcome
            )
            return {"outcome": outcome, "detail": detail}
            
        except httpx.ReadTimeout as e:
            action.status = "FAILED"
            outcome = "retry_pending"
            detail = "Gateway read timeout occurred."
            action.response_payload = json.dumps({
                "outcome": outcome,
                "detail": detail,
                "error": "ReadTimeout",
                "message": str(e)
            })
            transition_case_status(db, case, "RETRY_PENDING", "Provider read timeout. Retry pending.")
            
            log_audit_event(
                db, action="provider_timeout", record_id=payment.record_id,
                customer_id=customer.customer_id, case_id=case.case_id,
                idempotency_key=idempotency_key, provider_result="Read Timeout",
                outcome=outcome
            )
            return {"outcome": outcome, "detail": detail}
            
        except httpx.HTTPStatusError as e:
            action.status = "FAILED"
            outcome = "escalated"
            detail = f"Gateway API returned HTTP status {e.response.status_code}"
            action.response_payload = json.dumps({
                "outcome": outcome,
                "detail": detail,
                "error": "HTTPStatusError",
                "status_code": e.response.status_code
            })
            transition_case_status(db, case, "ESCALATED", f"Gateway API returned {e.response.status_code} Internal Server Error.")
            
            log_audit_event(
                db, action="provider_error", record_id=payment.record_id,
                customer_id=customer.customer_id, case_id=case.case_id,
                idempotency_key=idempotency_key, provider_result=f"HTTP Error {e.response.status_code}",
                outcome=outcome
            )
            return {"outcome": outcome, "detail": detail}
            
        except Exception as e:
            action.status = "FAILED"
            outcome = "failed"
            detail = str(e)
            action.response_payload = json.dumps({
                "outcome": outcome,
                "detail": detail,
                "error": "GenericException",
                "message": str(e)
            })
            transition_case_status(db, case, "ESCALATED", f"Execution failed: {str(e)}")
            
            log_audit_event(
                db, action="execution_failed", record_id=payment.record_id,
                customer_id=customer.customer_id, case_id=case.case_id,
                idempotency_key=idempotency_key, provider_result=str(e),
                outcome="escalated"
            )
            return {"outcome": outcome, "detail": detail}

    elif action_type in ["send_payment_reminder", "request_payment_method_update", "request_mandate_reauthorization"]:
        # Verify comms guardrails again just in case
        if customer.opted_out_of_comms or not policy.comms_enabled:
            action.status = "BLOCKED"
            transition_case_status(db, case, "BLOCKED", "Customer has opted out of communications.")
            
            log_audit_event(
                db, action="execution_blocked", record_id=payment.record_id,
                customer_id=customer.customer_id, case_id=case.case_id,
                reason="Communication opt-out guardrail matched during execution.",
                outcome="blocked"
            )
            return {"outcome": "blocked", "detail": "Communication blocked by policy."}

        # Generate comm content
        ai_provider = get_ai_provider()
        comm_info = {
            "customer_name": customer.name,
            "amount": payment.amount,
            "failure_reason": payment.failure_code.replace("_", " "),
            "language": "hinglish" if policy.hinglish_enabled else "english",
            "merchant_tone": "polite"
        }
        message_body = ai_provider.generate_communication(comm_info)
        
        # Save communication notification
        notif = Notification(
            customer_id=customer.customer_id,
            case_id=case.case_id,
            channel="sms" if action_type == "send_payment_reminder" else "email",
            language=comm_info["language"],
            content=message_body,
            status="SENT",
            sent_at=datetime.utcnow()
        )
        db.add(notif)
        
        action.status = "SUCCESS"
        action.comms_channel = notif.channel
        action.comms_language = notif.language
        action.comms_content = message_body
        
        # Once comms are sent, we move state to RETRY_PENDING or FAILED depending on retry limits
        transition_case_status(db, case, "RETRY_PENDING")
        
        outcome = "retry_pending"
        detail = "Communication sent successfully. Pending retry/update."
        action.response_payload = json.dumps({
            "outcome": outcome,
            "detail": detail,
            "channel": notif.channel,
            "language": notif.language,
            "content": message_body
        })
        db.commit()
        
        log_audit_event(
            db, action="communication_sent", record_id=payment.record_id,
            customer_id=customer.customer_id, case_id=case.case_id,
            idempotency_key=idempotency_key, outcome=outcome
        )
        return {"outcome": outcome, "detail": detail}

    else:
        # no_action or escalate_to_human
        action.status = "SUCCESS"
        transition_case_status(
            db, 
            case, 
            "ESCALATED" if action_type == "escalate_to_human" else "FAILED",
            "Escalated to human operator." if action_type == "escalate_to_human" else "No action recommended."
        )
        
        outcome = "escalated" if action_type == "escalate_to_human" else "failed"
        detail = "Escalated to human operator." if action_type == "escalate_to_human" else "No action recommended."
        action.response_payload = json.dumps({
            "outcome": outcome,
            "detail": detail
        })
        db.commit()
        
        log_audit_event(
            db, action="execution_completed", record_id=payment.record_id,
            customer_id=customer.customer_id, case_id=case.case_id,
            idempotency_key=idempotency_key, outcome=outcome
        )
        return {"outcome": outcome, "detail": detail}
