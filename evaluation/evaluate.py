import os
import sys
import json
from datetime import datetime
from sqlalchemy.orm import Session

# Add project root to python path to import models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal, engine, Base
from backend.app.models import PaymentRecord, EvaluationRun, Customer, PolicySettings
from backend.app.services.classifier import classify_failure_deterministically
from backend.app.ai.ai_provider import MockAIProvider
from backend.app.services.guardrails import validate_action_guardrails

def run_evaluation():
    db = SessionLocal()
    
    # 1. Fetch held-out records (200 records)
    held_out_payments = db.query(PaymentRecord).filter(
        PaymentRecord.is_held_out == True
    ).all()
    
    if not held_out_payments:
        print("No evaluation dataset found. Please run data/generate_data.py first.")
        db.close()
        return

    print(f"Starting evaluation on {len(held_out_payments)} held-out records...")
    
    # Setup mock AI provider for evaluation (consistent and fast)
    ai_provider = MockAIProvider()
    
    # Track statistics for Rules-only and AI-assisted
    stats = {
        "rules_only": {
            "tp": 0, "fp": 0, "fn": 0, "tn": 0,
            "revenue_recovered": 0.0,
            "revenue_at_risk": 0.0,
            "guardrail_blocks": 0,
            "human_escalations": 0,
            "total_attempts": 0
        },
        "ai_assisted": {
            "tp": 0, "fp": 0, "fn": 0, "tn": 0,
            "revenue_recovered": 0.0,
            "revenue_at_risk": 0.0,
            "guardrail_blocks": 0,
            "human_escalations": 0,
            "total_attempts": 0
        }
    }
    
    # Define what is "actionable" (positive prediction)
    actionable_actions = {
        "retry_payment", "schedule_retry", "send_payment_reminder",
        "request_payment_method_update", "request_mandate_reauthorization"
    }
    
    total_recoverable_revenue = 0.0
    for p in held_out_payments:
        if p.actually_recoverable:
            total_recoverable_revenue += p.amount
            
    # Evaluation loop
    for pay in held_out_payments:
        customer = pay.customer
        
        # --- 1. Rules-only Mode ---
        # Deterministic check
        action, confidence, is_ambiguous = classify_failure_deterministically(pay.failure_code)
        source = "rules"
        
        # If rules mode encounters ambiguous, it falls back to escalate_to_human (no AI)
        if is_ambiguous:
            action = "escalate_to_human"
            confidence = 1.0
            source = "rules"
            
        # Create a temp mock case structure for guardrail check
        from backend.app.models import RecoveryCase
        temp_case = RecoveryCase(payment=pay, retry_count=0)
        
        # Apply guardrails
        allowed, override_state, reason = validate_action_guardrails(db, temp_case, action, confidence, source)
        
        rules_action = action
        rules_status = "APPROVED"
        if not allowed:
            rules_status = override_state
            if override_state == "BLOCKED":
                rules_action = "no_action"
                stats["rules_only"]["guardrail_blocks"] += 1
            else:
                rules_action = "escalate_to_human"
                stats["rules_only"]["human_escalations"] += 1
                
        is_rules_actionable = rules_action in actionable_actions
        
        # Evaluate against ground truth
        if is_rules_actionable:
            stats["rules_only"]["total_attempts"] += 1
            if pay.actually_recoverable and rules_action == pay.best_action:
                stats["rules_only"]["tp"] += 1
                stats["rules_only"]["revenue_recovered"] += pay.amount
            else:
                stats["rules_only"]["fp"] += 1
        else:
            if pay.actually_recoverable:
                stats["rules_only"]["fn"] += 1
            else:
                stats["rules_only"]["tn"] += 1
                
        # --- 2. AI-assisted Mode ---
        # Deterministic first
        ai_action, ai_confidence, ai_is_ambiguous = classify_failure_deterministically(pay.failure_code)
        ai_source = "rules"
        
        if ai_is_ambiguous:
            payment_info = {
                "record_id": pay.record_id,
                "customer_id": pay.customer_id,
                "amount": pay.amount,
                "currency": pay.currency,
                "failure_code": pay.failure_code,
                "retry_count_so_far": pay.retry_count_so_far,
                "payment_method": pay.payment_method,
                "days_since_failure": pay.days_since_failure,
                "previous_success_count": customer.previous_success_count,
                "previous_failure_count": customer.previous_failure_count,
                "previous_refund_requested": customer.previous_refund_requested,
                "opted_out_of_comms": customer.opted_out_of_comms
            }
            ai_recommendation = ai_provider.recommend_recovery(payment_info)
            ai_action = ai_recommendation.recommended_action
            ai_confidence = ai_recommendation.confidence
            ai_source = "ai"
            
        # Apply guardrails
        ai_allowed, ai_override_state, ai_guardrail_reason = validate_action_guardrails(
            db, temp_case, ai_action, ai_confidence, ai_source
        )
        
        final_ai_action = ai_action
        if not ai_allowed:
            if ai_override_state == "BLOCKED":
                final_ai_action = "no_action"
                stats["ai_assisted"]["guardrail_blocks"] += 1
            else:
                final_ai_action = "escalate_to_human"
                stats["ai_assisted"]["human_escalations"] += 1
                
        is_ai_actionable = final_ai_action in actionable_actions
        
        # Evaluate against ground truth
        if is_ai_actionable:
            stats["ai_assisted"]["total_attempts"] += 1
            if pay.actually_recoverable and final_ai_action == pay.best_action:
                stats["ai_assisted"]["tp"] += 1
                stats["ai_assisted"]["revenue_recovered"] += pay.amount
            else:
                stats["ai_assisted"]["fp"] += 1
        else:
            if pay.actually_recoverable:
                stats["ai_assisted"]["fn"] += 1
            else:
                stats["ai_assisted"]["tn"] += 1
                
    # Calculate metrics
    def calculate_metrics_dict(s, label):
        tp, fp, fn, tn = s["tp"], s["fp"], s["fn"], s["tn"]
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        
        # Flat false positive cost (e.g. ₹50 per failed recovery attempt / SMS spam)
        fp_cost = fp * 50.0
        
        recovery_rate = (tp / len(held_out_payments) * 100.0)
        
        return {
            "mode": label,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "recovery_attempts": s["total_attempts"],
            "successful_recoveries": tp,
            "revenue_recovered": s["revenue_recovered"],
            "recovery_rate": round(recovery_rate, 2),
            "false_positive_cost": fp_cost,
            "guardrail_blocks": s["guardrail_blocks"],
            "human_escalations": s["human_escalations"]
        }
        
    rules_metrics = calculate_metrics_dict(stats["rules_only"], "Rules-only")
    ai_metrics = calculate_metrics_dict(stats["ai_assisted"], "AI-assisted")
    
    print("\n--- Evaluation Results ---")
    print(f"Rules Only  => Precision: {rules_metrics['precision']:.4f}, Recall: {rules_metrics['recall']:.4f}, F1: {rules_metrics['f1']:.4f}")
    print(f"AI Assisted => Precision: {ai_metrics['precision']:.4f}, Recall: {ai_metrics['recall']:.4f}, F1: {ai_metrics['f1']:.4f}")
    print(f"Revenue Recovered => Rules: INR {rules_metrics['revenue_recovered']:.2f}, AI: INR {ai_metrics['revenue_recovered']:.2f} (out of INR {total_recoverable_revenue:.2f} recoverable)")

    # 3. Save to results/final_results.json
    results_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../results"))
    os.makedirs(results_dir, exist_ok=True)
    
    final_results = {
        "dataset_size": db.query(PaymentRecord).count(),
        "held_out_size": len(held_out_payments),
        "precision": ai_metrics["precision"],
        "recall": ai_metrics["recall"],
        "f1": ai_metrics["f1"],
        "recovery_attempts": ai_metrics["recovery_attempts"],
        "successful_recoveries": ai_metrics["successful_recoveries"],
        "revenue_at_risk": sum([p.amount for p in held_out_payments]),
        "revenue_recovered": ai_metrics["revenue_recovered"],
        "guardrail_blocks": ai_metrics["guardrail_blocks"],
        "human_escalations": ai_metrics["human_escalations"],
        "comparison": {
            "rules_only": rules_metrics,
            "ai_assisted": ai_metrics
        }
    }
    
    with open(os.path.join(results_dir, "final_results.json"), "w") as f:
        json.dump(final_results, f, indent=2)
        
    # 4. Insert into database
    run = EvaluationRun(
        dataset_size=final_results["dataset_size"],
        held_out_size=final_results["held_out_size"],
        precision=ai_metrics["precision"],
        recall=ai_metrics["recall"],
        f1=ai_metrics["f1"],
        recovery_attempts=ai_metrics["recovery_attempts"],
        successful_recoveries=ai_metrics["successful_recoveries"],
        revenue_at_risk=final_results["revenue_at_risk"],
        revenue_recovered=ai_metrics["revenue_recovered"],
        guardrail_blocks=ai_metrics["guardrail_blocks"],
        human_escalations=ai_metrics["human_escalations"],
        comparison_data=json.dumps(final_results["comparison"])
    )
    db.add(run)
    db.commit()
    db.close()
    print("Evaluation completed and results saved to database.")

if __name__ == "__main__":
    run_evaluation()
