from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from backend.app.database import engine, Base, get_db
from backend.app.models import (
    PaymentRecord, RecoveryCase, RecoveryAction, AuditEvent,
    PolicySettings, EvaluationRun, Customer, Order, Notification, PaymentAttempt
)
from backend.app.schemas import (
    PaymentRecordSchema, RecoveryCaseSchema, AuditEventSchema,
    PolicySettingsSchema, PolicyUpdateSchema, SimulationRequestSchema,
    AnalyzeRequestSchema, BatchExecuteRequestSchema, DashboardMetricsSchema,
    EvaluationRunSchema
)
from backend.app.services.metrics_service import calculate_dashboard_metrics
from backend.app.services.recovery_engine import ingest_failed_payment
from backend.app.services.executor import execute_recovery_action
from backend.app.services.verifier import verify_payment_status
from backend.app.services.guardrails import get_current_policy
from backend.app.services.audit_service import log_audit_event
from backend.app.integrations.payment_adapter import MockRazorpayAdapter

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RecoverAI - AI Revenue Recovery API")

from backend.app.config import settings

# Configure CORS origins based on environment settings
origins = []
if settings.FRONTEND_ORIGIN:
    origins.extend([o.strip() for o in settings.FRONTEND_ORIGIN.split(",") if o.strip()])
else:
    # Default to standard local development origins
    origins.extend([
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/dashboard", response_model=DashboardMetricsSchema)
def get_dashboard(db: Session = Depends(get_db)):
    try:
        # Ingest any failed payments that don't have recovery cases yet
        # to ensure dashboard shows correct data
        unprocessed_payments = db.query(PaymentRecord).filter(
            ~PaymentRecord.record_id.in_(
                db.query(RecoveryCase.payment_record_id)
            ),
            PaymentRecord.is_held_out == False
        ).all()
        for pay in unprocessed_payments:
            ingest_failed_payment(db, pay.record_id)
            
        metrics = calculate_dashboard_metrics(db)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/payments", response_model=List[PaymentRecordSchema])
def get_payments(
    status: Optional[str] = None,
    failure_code: Optional[str] = None,
    is_held_out: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(PaymentRecord)
    if status:
        query = query.filter(PaymentRecord.status == status)
    if failure_code:
        query = query.filter(PaymentRecord.failure_code == failure_code)
    if is_held_out is not None:
        query = query.filter(PaymentRecord.is_held_out == is_held_out)
    return query.order_by(PaymentRecord.failure_timestamp.desc()).all()

@app.get("/api/payments/{id}", response_model=PaymentRecordSchema)
def get_payment(id: str, db: Session = Depends(get_db)):
    pay = db.query(PaymentRecord).filter(PaymentRecord.record_id == id).first()
    if not pay:
        raise HTTPException(status_code=404, detail="Payment record not found")
    return pay

@app.get("/api/recovery/cases", response_model=List[RecoveryCaseSchema])
def get_recovery_cases(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(RecoveryCase)
    if status:
        query = query.filter(RecoveryCase.status == status)
    return query.order_by(RecoveryCase.created_at.desc()).all()

@app.get("/api/recovery/cases/{id}", response_model=RecoveryCaseSchema)
def get_recovery_case(id: str, db: Session = Depends(get_db)):
    case = db.query(RecoveryCase).filter(RecoveryCase.case_id == id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Recovery case not found")
    return case

@app.post("/api/recovery/analyze")
def analyze_payments(req: AnalyzeRequestSchema, db: Session = Depends(get_db)):
    ids = req.payment_record_ids
    if not ids:
        # If no ids provided, fetch all non-held-out failed payments that don't have cases
        payments = db.query(PaymentRecord).filter(
            PaymentRecord.status == "FAILED",
            PaymentRecord.is_held_out == False,
            ~PaymentRecord.record_id.in_(
                db.query(RecoveryCase.payment_record_id)
            )
        ).all()
        ids = [p.record_id for p in payments]
        
    created_cases = []
    for pay_id in ids:
        try:
            case = ingest_failed_payment(db, pay_id)
            created_cases.append(case.case_id)
        except Exception as e:
            # Continue processing others, log the error
            print(f"Error analyzing payment {pay_id}: {e}")
            
    return {"message": f"Successfully analyzed {len(created_cases)} payments", "case_ids": created_cases}

from fastapi import Header

@app.post("/api/recovery/{id}/execute")
def execute_case(id: str, db: Session = Depends(get_db), x_idempotency_key: Optional[str] = Header(None)):
    case = db.query(RecoveryCase).filter(RecoveryCase.case_id == id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Recovery case not found")
        
    res = execute_recovery_action(db, case.case_id, idempotency_key=x_idempotency_key)
    return res

@app.post("/api/recovery/batch")
def execute_batch(req: BatchExecuteRequestSchema, db: Session = Depends(get_db)):
    success_count = 0
    results = {}
    for cid in req.case_ids:
        try:
            res = execute_recovery_action(db, cid)
            results[cid] = res
            if res.get("outcome") == "recovered":
                success_count += 1
        except Exception as e:
            results[cid] = {"outcome": "failed", "detail": str(e)}
            
    return {
        "message": f"Processed batch of {len(req.case_ids)} cases. {success_count} recovered.",
        "results": results
    }

@app.post("/api/recovery/simulate")
def simulate_recovery(req: SimulationRequestSchema, db: Session = Depends(get_db)):
    payment = db.query(PaymentRecord).filter(PaymentRecord.record_id == req.payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")
        
    # Get or create recovery case
    case = db.query(RecoveryCase).filter(RecoveryCase.payment_record_id == payment.record_id).first()
    if not case:
        case = ingest_failed_payment(db, payment.record_id)
        
    # Run the action with the forced override
    res = execute_recovery_action(db, case.case_id, scenario_override=req.scenario)
    return res

@app.get("/api/audit", response_model=List[AuditEventSchema])
def get_audit_trail(
    action: Optional[str] = None,
    record_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AuditEvent)
    if action:
        query = query.filter(AuditEvent.action == action)
    if record_id:
        query = query.filter(AuditEvent.record_id == record_id)
    return query.order_by(AuditEvent.timestamp.desc()).all()

@app.get("/api/evaluation", response_model=List[EvaluationRunSchema])
def get_evaluation_runs(db: Session = Depends(get_db)):
    return db.query(EvaluationRun).order_by(EvaluationRun.timestamp.desc()).all()

@app.get("/api/policies", response_model=PolicySettingsSchema)
def get_policies(db: Session = Depends(get_db)):
    policy = get_current_policy(db)
    return policy

@app.put("/api/policies", response_model=PolicySettingsSchema)
def update_policies(req: PolicyUpdateSchema, db: Session = Depends(get_db)):
    policy = get_current_policy(db)
    
    updates = req.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(policy, key, value)
        
    db.commit()
    db.refresh(policy)
    
    # Audit log policy change
    log_audit_event(
        db, action="policy_updated",
        reason=f"Merchant updated policy: {updates}"
    )
    
    return policy

@app.get("/api/integrations/razorpay/status")
def get_integration_status():
    from backend.app.config import settings
    import httpx
    
    mode = settings.RAZORPAY_MODE
    if mode == "test":
        configured = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
        reachable = False
        authenticated = False
        if configured:
            try:
                auth = (settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
                r = httpx.get("https://api.razorpay.com/v1/payments?count=1", auth=auth, timeout=3.0)
                reachable = True
                authenticated = (r.status_code == 200)
            except httpx.HTTPStatusError as e:
                reachable = True
                authenticated = (e.response.status_code != 401)
            except Exception:
                reachable = False
                authenticated = False
        return {
            "mode": "test",
            "configured": configured,
            "reachable": reachable,
            "authenticated": authenticated
        }
    else:
        return {
            "mode": "mock",
            "configured": True,
            "reachable": True,
            "authenticated": True
        }

@app.post("/api/reset")
def reset_db_simulations(db: Session = Depends(get_db)):
    """
    Utility endpoint for the demo: resets payment statuses, clears recovery actions/cases, and clears mock adapter cache.
    """
    try:
        # Clear recovery actions, cases, audits, payment attempts, notifications
        db.query(Notification).delete()
        db.query(PaymentAttempt).delete()
        db.query(RecoveryAction).delete()
        db.query(RecoveryCase).delete()
        db.query(AuditEvent).delete()
        
        # Reset payment records to FAILED
        payments = db.query(PaymentRecord).all()
        for p in payments:
            p.status = "FAILED"
            p.retry_count_so_far = 0
            
        db.commit()
        MockRazorpayAdapter.clear_overrides()
        
        log_audit_event(db, action="system_reset", reason="Database and simulation states reset to seed defaults.")
        return {"status": "success", "message": "Simulation states reset successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import os
from fastapi.staticfiles import StaticFiles

dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))
if os.path.exists(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="frontend")
