import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import Customer, Order, PaymentRecord, RecoveryCase, RecoveryAction
from backend.app.services.deduplication import check_duplicate_payment
from backend.app.services.guardrails import validate_action_guardrails, get_current_policy
from backend.app.services.classifier import classify_failure_deterministically
from backend.app.services.decision_engine import determine_recovery_action
from backend.app.services.executor import execute_recovery_action
from backend.app.services.metrics_service import calculate_dashboard_metrics
from backend.app.services.recovery_engine import ingest_failed_payment

# Set up clean in-memory test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # Create a default policy settings
        from backend.app.models import PolicySettings
        policy = PolicySettings(
            max_retries=3,
            retry_cooldown=3600,
            auto_recovery_ceiling=50000.0,
            human_approval_threshold=50000.0,
            daily_action_limit=100,
            comms_enabled=True,
            hinglish_enabled=True
        )
        db.add(policy)
        db.commit()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def create_mock_payment(db, record_id="pay_test_1", amount=1000.0, failure_code="insufficient_funds", opted_out=False, refund_requested=False, retry_count=0):
    cust_id = f"cust_{record_id}"
    customer = Customer(
        customer_id=cust_id,
        name="Test Customer",
        email="test@example.com",
        phone="+919999900000",
        opted_out_of_comms=opted_out,
        previous_refund_requested=refund_requested,
        previous_success_count=5,
        previous_failure_count=1
    )
    db.add(customer)
    
    order_id = f"order_{record_id}"
    order = Order(
        order_id=order_id,
        customer_id=cust_id,
        amount=amount,
        currency="INR"
    )
    db.add(order)
    
    payment = PaymentRecord(
        record_id=record_id,
        customer_id=cust_id,
        order_id=order_id,
        type="payment",
        amount=amount,
        currency="INR",
        failure_code=failure_code,
        failure_timestamp=datetime.utcnow(),
        retry_count_so_far=retry_count,
        payment_method="card",
        status="FAILED",
        actually_recoverable=True,
        best_action="retry_payment"
    )
    db.add(payment)
    db.commit()
    return payment

def test_deterministic_classification():
    action, confidence, is_ambiguous = classify_failure_deterministically("insufficient_funds")
    assert action == "retry_payment"
    assert confidence == 1.0
    assert not is_ambiguous

    action, confidence, is_ambiguous = classify_failure_deterministically("card_expired")
    assert action == "request_payment_method_update"
    
    action, confidence, is_ambiguous = classify_failure_deterministically("issuer_declined_generic")
    assert is_ambiguous
    assert action is None

def test_deduplication(db_session):
    p1 = create_mock_payment(db_session, "pay_1", amount=1200.0)
    
    # Ingest case for p1 so deduplication registers an existing case
    case1 = ingest_failed_payment(db_session, p1.record_id)
    
    # Create near-duplicate payment record 1 minute later
    p2 = PaymentRecord(
        record_id="pay_1_dup",
        customer_id=p1.customer_id,
        order_id=p1.order_id,
        type=p1.type,
        amount=p1.amount,
        currency=p1.currency,
        failure_code=p1.failure_code,
        failure_timestamp=p1.failure_timestamp + timedelta(minutes=1),
        retry_count_so_far=0,
        payment_method=p1.payment_method,
        status="FAILED"
    )
    db_session.add(p2)
    db_session.commit()
    
    is_dup, reason = check_duplicate_payment(db_session, p2)
    assert is_dup
    assert "Duplicate" in reason

def test_guardrails_refund_requested(db_session):
    # Customer has refund requested
    p = create_mock_payment(db_session, "pay_refund", refund_requested=True)
    case = ingest_failed_payment(db_session, p.record_id)
    
    # Check that case is BLOCKED by refund guardrail
    assert case.status == "BLOCKED"
    assert "Refund was previously requested" in case.block_reason

def test_guardrails_high_value(db_session):
    # Payment exceeds 50,000 INR limit
    p = create_mock_payment(db_session, "pay_high", amount=65000.0)
    case = ingest_failed_payment(db_session, p.record_id)
    
    # Check that case is ESCALATED
    assert case.status == "ESCALATED"
    assert "High-value transaction" in case.escalation_reason

def test_guardrails_comms_opt_out(db_session):
    # Customer opted out of communications, and action is request_payment_method_update
    p = create_mock_payment(db_session, "pay_opt_out", failure_code="card_expired", opted_out=True)
    case = ingest_failed_payment(db_session, p.record_id)
    
    assert case.status == "BLOCKED"
    assert "Customer has opted out of communication" in case.block_reason

def test_idempotency(db_session):
    policy = get_current_policy(db_session)
    policy.auto_recovery_ceiling = 0.0
    db_session.commit()
    
    p = create_mock_payment(db_session, "pay_idem")
    case = ingest_failed_payment(db_session, p.record_id)
    
    key = "recovery:pay_idem:custom_test"
    
    # First execution
    res1 = execute_recovery_action(db_session, case.case_id, scenario_override="success", idempotency_key=key)
    assert res1["outcome"] == "recovered"
    
    # Second execution of same case (should trigger idempotency key match and return previous outcome)
    res2 = execute_recovery_action(db_session, case.case_id, scenario_override="success", idempotency_key=key)
    assert res2["outcome"] == "recovered"
    assert res2.get("cached") is True

def test_state_transitions(db_session):
    p = create_mock_payment(db_session, "pay_state")
    
    # Ingest and move from DETECTED -> APPROVED
    # (Since amount 1000 <= 50000 limit, it will automatically execute inside ingest if eligible, 
    # but let's check its lifecycle. In ingest_failed_payment, if should_auto_execute is True, 
    # it executes and moves to RECOVERED or FAILED)
    case = ingest_failed_payment(db_session, p.record_id)
    
    # It should have auto-executed and recovered successfully
    assert case.status == "RECOVERED"
    assert p.status == "RECOVERED"

def test_metrics_calculation(db_session):
    policy = get_current_policy(db_session)
    policy.auto_recovery_ceiling = 0.0
    db_session.commit()
    
    p1 = create_mock_payment(db_session, "pay_m1", amount=1000.0)
    p2 = create_mock_payment(db_session, "pay_m2", amount=2000.0)
    
    # Ingest them
    ingest_failed_payment(db_session, p1.record_id)
    ingest_failed_payment(db_session, p2.record_id)
    
    # Set one as recovered
    p1.status = "RECOVERED"
    case1 = db_session.query(RecoveryCase).filter(RecoveryCase.payment_record_id == p1.record_id).first()
    case1.status = "RECOVERED"
    
    # Set one as escalated (p2 remains FAILED payment)
    p2.status = "FAILED"
    case2 = db_session.query(RecoveryCase).filter(RecoveryCase.payment_record_id == p2.record_id).first()
    case2.status = "ESCALATED"
    
    db_session.commit()
    
    metrics = calculate_dashboard_metrics(db_session)
    # Revenue at risk should only count payments in FAILED status (p2 is still FAILED)
    assert metrics["revenue_at_risk"] == 2000.0
    assert metrics["revenue_recovered"] == 1000.0
    assert metrics["successful_recoveries"] == 1
    assert metrics["human_escalations"] == 1

def test_guardrails_low_confidence(db_session):
    p = create_mock_payment(db_session, "pay_low_conf")
    case = ingest_failed_payment(db_session, p.record_id)
    allowed, state, reason = validate_action_guardrails(db_session, case, "retry_payment", 0.50, "ai")
    assert not allowed
    assert state == "ESCALATED"
    assert "AI confidence" in reason

def test_guardrails_daily_action_limit(db_session):
    policy = get_current_policy(db_session)
    policy.daily_action_limit = 2
    db_session.commit()
    
    p = create_mock_payment(db_session, "pay_limit_test")
    case = ingest_failed_payment(db_session, p.record_id)
    
    a1 = RecoveryAction(case_id=case.case_id, action_type="retry_payment", status="SUCCESS", idempotency_key="k1", executed_at=datetime.utcnow())
    a2 = RecoveryAction(case_id=case.case_id, action_type="retry_payment", status="SUCCESS", idempotency_key="k2", executed_at=datetime.utcnow())
    db_session.add(a1)
    db_session.add(a2)
    db_session.commit()
    
    allowed, state, reason = validate_action_guardrails(db_session, case, "retry_payment", 0.9, "rules")
    assert not allowed
    assert state == "ESCALATED"
    assert "Daily automatic action limit" in reason

def test_malformed_ai_unsupported_action():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        # recommended_action is a Literal type, invalid action throws ValidationError
        from backend.app.ai.ai_provider import AIRecommendation
        AIRecommendation(
            classification="recoverable",
            recommended_action="invalid_recovery_action",
            confidence=0.9,
            reason="invalid"
        )

def test_unknown_payment_state(db_session):
    policy = get_current_policy(db_session)
    policy.auto_recovery_ceiling = 0.0
    db_session.commit()
    
    p = create_mock_payment(db_session, "pay_unknown_state")
    case = ingest_failed_payment(db_session, p.record_id)
    
    res = execute_recovery_action(db_session, case.case_id, scenario_override="unknown_payment_state")
    assert res["outcome"] == "escalated"
    assert case.status == "STATE_UNKNOWN"

def test_ai_unavailable_fallback(db_session):
    p = create_mock_payment(db_session, "pay_outage", failure_code="issuer_declined_generic")
    
    import unittest.mock as mock
    from backend.app.ai.ai_provider import MockAIProvider
    
    with mock.patch.object(MockAIProvider, "recommend_recovery", side_effect=Exception("AI Connection Outage")):
        case = ingest_failed_payment(db_session, p.record_id)
        assert case.recommended_action == "escalate_to_human"
        assert case.status == "ESCALATED"
        # The guardrail receives the escalate_to_human recommendation and routes to ESCALATED
        assert case.escalation_reason is not None

def test_malformed_ai_output():
    import pytest
    from pydantic import ValidationError
    from backend.app.ai.ai_provider import AIRecommendation
    
    with pytest.raises(ValidationError):
        AIRecommendation(
            classification="recoverable",
            recommended_action="retry_payment",
            confidence=1.5,
            reason="valid"
        )
        
    with pytest.raises(ValidationError):
        AIRecommendation(
            classification="recoverable",
            recommended_action="retry_payment",
            confidence=-0.1,
            reason="valid"
        )

    with pytest.raises(ValidationError):
        AIRecommendation(
            classification="recoverable",
            recommended_action="retry_payment",
            confidence=0.9,
            reason="valid",
            extra_malicious_field="hack"
        )

def test_provider_timeout(db_session):
    policy = get_current_policy(db_session)
    policy.auto_recovery_ceiling = 0.0
    db_session.commit()
    
    p = create_mock_payment(db_session, "pay_timeout_reg")
    case = ingest_failed_payment(db_session, p.record_id)
    
    res = execute_recovery_action(db_session, case.case_id, scenario_override="timeout")
    assert res["outcome"] == "retry_pending"
    assert case.status == "RETRY_PENDING"

def test_provider_http_500(db_session):
    policy = get_current_policy(db_session)
    policy.auto_recovery_ceiling = 0.0
    db_session.commit()
    
    p = create_mock_payment(db_session, "pay_500_reg")
    case = ingest_failed_payment(db_session, p.record_id)
    
    # Correct adapter scenario code is "500" not "gateway_500"
    res = execute_recovery_action(db_session, case.case_id, scenario_override="500")
    assert res["outcome"] == "escalated"
    assert case.status == "ESCALATED"
    assert "Gateway API returned" in case.escalation_reason

def test_already_completed_payment(db_session):
    policy = get_current_policy(db_session)
    policy.auto_recovery_ceiling = 0.0
    db_session.commit()
    
    p = create_mock_payment(db_session, "pay_already_captured")
    case = ingest_failed_payment(db_session, p.record_id)
    
    # Simulate the payment being already captured by setting status in DB
    p.status = "RECOVERED"
    db_session.commit()
    
    res = execute_recovery_action(db_session, case.case_id)
    assert res["outcome"] == "already_completed"
    assert case.status == "RECOVERED"

def test_verification_failure(db_session):
    policy = get_current_policy(db_session)
    policy.auto_recovery_ceiling = 0.0
    db_session.commit()
    
    p = create_mock_payment(db_session, "pay_verif_fail")
    case = ingest_failed_payment(db_session, p.record_id)
    
    # "failed_retry" scenario causes adapter to return failed status
    res = execute_recovery_action(db_session, case.case_id, scenario_override="failed_retry")
    assert res["outcome"] == "still_failed"
    assert case.status == "FAILED"

def test_batch_recovery(db_session):
    policy = get_current_policy(db_session)
    policy.auto_recovery_ceiling = 100000.0
    db_session.commit()
    
    p1 = create_mock_payment(db_session, "pay_b1")
    p2 = create_mock_payment(db_session, "pay_b2")
    
    case1 = ingest_failed_payment(db_session, p1.record_id)
    case2 = ingest_failed_payment(db_session, p2.record_id)
    
    assert case1.status == "RECOVERED"
    assert case2.status == "RECOVERED"

def test_policy_update_audit(db_session):
    from backend.app.services.audit_service import log_audit_event
    from backend.app.models import AuditEvent
    
    policy = get_current_policy(db_session)
    policy.auto_recovery_ceiling = 25000.0
    db_session.commit()
    
    log_audit_event(
        db_session,
        action="policy_updated",
        record_id="system",
        reason="Updated auto recovery ceiling threshold to ₹25,000"
    )
    
    audit = db_session.query(AuditEvent).filter(AuditEvent.action == "policy_updated").first()
    assert audit is not None
    assert "₹25,000" in audit.reason

def test_invalid_state_transitions(db_session):
    p = create_mock_payment(db_session, "pay_invalid_trans")
    case = ingest_failed_payment(db_session, p.record_id)
    
    case.status = "DETECTED"
    db_session.commit()
    
    from backend.app.services.recovery_engine import transition_case_status
    import pytest
    with pytest.raises(ValueError):
        transition_case_status(db_session, case, "RECOVERED")

def test_ai_cannot_bypass_guardrails(db_session):
    # Refund protection check
    p = create_mock_payment(db_session, "pay_bypass_refund", refund_requested=True)
    case = ingest_failed_payment(db_session, p.record_id)
    assert case.status == "BLOCKED"
    assert "Refund was previously requested" in case.block_reason

    # Comms opt-out check
    p2 = create_mock_payment(db_session, "pay_bypass_comms", failure_code="card_expired", opted_out=True)
    case2 = ingest_failed_payment(db_session, p2.record_id)
    assert case2.status == "BLOCKED"
    assert "Customer has opted out of communication" in case2.block_reason

    # High-value limit check
    p3 = create_mock_payment(db_session, "pay_bypass_high", amount=90000.0)
    case3 = ingest_failed_payment(db_session, p3.record_id)
    assert case3.status == "ESCALATED"
    assert "High-value transaction" in case3.escalation_reason

def test_mock_provider_methods(db_session):
    from backend.app.integrations.payment_adapter import MockRazorpayAdapter
    adapter = MockRazorpayAdapter()
    
    # 1. Test fetch_payment
    p = create_mock_payment(db_session, "pay_mock_m1", amount=150.0)
    details = adapter.fetch_payment(p.record_id, db=db_session)
    assert details["id"] == p.record_id
    assert details["status"] == "failed"
    assert details["amount"] == 15000
    
    # 2. Test capture_payment
    cap = adapter.capture_payment(p.record_id, 150.0)
    assert cap["status"] == "captured"
    
    # 3. Test verify_payment after capture
    ver = adapter.verify_payment(p.record_id)
    assert ver["status"] == "captured"
    
    # 4. Test fetch_order_payments
    pays = adapter.fetch_order_payments(p.order_id, db=db_session)
    assert len(pays) == 1
    assert pays[0]["id"] == p.record_id
    assert pays[0]["status"] == "captured"

def test_test_provider_credentials_check():
    from backend.app.integrations.payment_adapter import RazorpayTestAdapter, get_payment_adapter
    from backend.app.config import settings
    import pytest
    
    # Backup original config
    orig_mode = settings.RAZORPAY_MODE
    orig_id = settings.RAZORPAY_KEY_ID
    orig_secret = settings.RAZORPAY_KEY_SECRET
    
    try:
        # Test configuration validation failure
        settings.RAZORPAY_MODE = "test"
        settings.RAZORPAY_KEY_ID = ""
        settings.RAZORPAY_KEY_SECRET = ""
        
        with pytest.raises(ValueError) as exc:
            get_payment_adapter()
        assert "Missing Razorpay credentials" in str(exc.value)
        
        # Test successful instantiating with credentials configured
        settings.RAZORPAY_KEY_ID = "rzp_test_123"
        settings.RAZORPAY_KEY_SECRET = "secret_123"
        adapter = get_payment_adapter()
        assert isinstance(adapter, RazorpayTestAdapter)
        assert adapter.auth == ("rzp_test_123", "secret_123")
    finally:
        # Restore original config
        settings.RAZORPAY_MODE = orig_mode
        settings.RAZORPAY_KEY_ID = orig_id
        settings.RAZORPAY_KEY_SECRET = orig_secret

def test_test_provider_api_calls():
    import unittest.mock as mock
    from backend.app.integrations.payment_adapter import RazorpayTestAdapter
    from backend.app.config import settings
    
    orig_id = settings.RAZORPAY_KEY_ID
    orig_secret = settings.RAZORPAY_KEY_SECRET
    settings.RAZORPAY_KEY_ID = "rzp_test_mock"
    settings.RAZORPAY_KEY_SECRET = "secret_mock"
    
    try:
        adapter = RazorpayTestAdapter()
        
        with mock.patch("httpx.Client.get") as mock_get:
            # 1. Mock fetch_payment response
            mock_get.return_value = mock.MagicMock(
                status_code=200,
                json=lambda: {"id": "pay_test_1", "status": "authorized", "amount": 1000}
            )
            details = adapter.fetch_payment("pay_test_1")
            assert details["id"] == "pay_test_1"
            assert details["status"] == "authorized"
            mock_get.assert_called_once_with("https://api.razorpay.com/v1/payments/pay_test_1")
            
        with mock.patch("httpx.Client.get") as mock_get:
            # 2. Mock fetch_order_payments response
            mock_get.return_value = mock.MagicMock(
                status_code=200,
                json=lambda: {"entity": "collection", "items": [{"id": "pay_test_1"}]}
            )
            pays = adapter.fetch_order_payments("order_1")
            assert len(pays) == 1
            assert pays[0]["id"] == "pay_test_1"
            mock_get.assert_called_once_with("https://api.razorpay.com/v1/orders/order_1/payments")
            
        with mock.patch("httpx.Client.post") as mock_post:
            # 3. Mock capture_payment response
            mock_post.return_value = mock.MagicMock(
                status_code=200,
                json=lambda: {"id": "pay_test_1", "status": "captured", "amount": 1000}
            )
            cap = adapter.capture_payment("pay_test_1", 10.0)
            assert cap["status"] == "captured"
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert kwargs["json"]["amount"] == 1000
    finally:
        settings.RAZORPAY_KEY_ID = orig_id
        settings.RAZORPAY_KEY_SECRET = orig_secret

def test_executor_capture_validation(db_session):
    import unittest.mock as mock
    from backend.app.integrations.payment_adapter import RazorpayTestAdapter
    from backend.app.config import settings
    from backend.app.services.executor import execute_recovery_action
    
    orig_mode = settings.RAZORPAY_MODE
    orig_id = settings.RAZORPAY_KEY_ID
    orig_secret = settings.RAZORPAY_KEY_SECRET
    
    settings.RAZORPAY_MODE = "test"
    settings.RAZORPAY_KEY_ID = "rzp_test_abc"
    settings.RAZORPAY_KEY_SECRET = "secret_abc"
    
    try:
        p = create_mock_payment(db_session, "pay_verify_capture_val", amount=50.0)
        case = ingest_failed_payment(db_session, p.record_id)
        
        # Test 1: Fetch returns captured -> Skip capture (already completed)
        with mock.patch.object(RazorpayTestAdapter, "fetch_payment") as mock_fetch:
            mock_fetch.return_value = {"id": p.record_id, "status": "captured", "amount": 5000}
            res = execute_recovery_action(db_session, case.case_id)
            assert res["outcome"] == "already_completed"
            assert case.status == "RECOVERED"
            
        # Reset case status for next test
        case.status = "APPROVED"
        p.status = "FAILED"
        db_session.commit()
        
        # Test 2: Fetch returns failed -> Skip capture, escalate to human (do not capture failed)
        with mock.patch.object(RazorpayTestAdapter, "fetch_payment") as mock_fetch:
            mock_fetch.return_value = {"id": p.record_id, "status": "failed", "amount": 5000}
            res = execute_recovery_action(db_session, case.case_id)
            assert res["outcome"] == "still_failed"
            assert case.status == "FAILED"
            assert "Direct capture of a failed" in res["detail"]

        # Reset case status for next test
        case.status = "APPROVED"
        p.status = "FAILED"
        db_session.commit()
        
        # Test 3: Fetch returns authorized -> Executes capture successfully
        with mock.patch.object(RazorpayTestAdapter, "fetch_payment") as mock_fetch, \
             mock.patch.object(RazorpayTestAdapter, "capture_payment") as mock_capture:
            # First fetch returns authorized, second fetch after capture returns captured
            mock_fetch.side_effect = [
                {"id": p.record_id, "status": "authorized", "amount": 5000},
                {"id": p.record_id, "status": "authorized", "amount": 5000}, # fetch before capture
                {"id": p.record_id, "status": "captured", "amount": 5000}    # fetch after capture
            ]
            mock_capture.return_value = {"id": p.record_id, "status": "captured", "amount": 5000}
            res = execute_recovery_action(db_session, case.case_id)
            assert res["outcome"] == "recovered"
            assert case.status == "RECOVERED"
            assert p.status == "RECOVERED"
    finally:
        settings.RAZORPAY_MODE = orig_mode
        settings.RAZORPAY_KEY_ID = orig_id
        settings.RAZORPAY_KEY_SECRET = orig_secret

def test_integration_status_route():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.config import settings
    import unittest.mock as mock
    
    client = TestClient(app)
    
    orig_mode = settings.RAZORPAY_MODE
    orig_id = settings.RAZORPAY_KEY_ID
    orig_secret = settings.RAZORPAY_KEY_SECRET
    
    try:
        # 1. Test mock mode
        settings.RAZORPAY_MODE = "mock"
        r = client.get("/api/integrations/razorpay/status")
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "mock"
        assert data["configured"] is True
        assert data["reachable"] is True
        # Verify secrets are NOT exposed
        assert "key_secret" not in data
        assert "key_id" not in data
        
        # 2. Test test mode (unconfigured)
        settings.RAZORPAY_MODE = "test"
        settings.RAZORPAY_KEY_ID = ""
        settings.RAZORPAY_KEY_SECRET = ""
        r2 = client.get("/api/integrations/razorpay/status")
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["mode"] == "test"
        assert data2["configured"] is False
        assert data2["reachable"] is False
        
        # 3. Test test mode (configured & reachable)
        settings.RAZORPAY_KEY_ID = "rzp_test_ok"
        settings.RAZORPAY_KEY_SECRET = "secret_ok"
        with mock.patch("httpx.get") as mock_get:
            mock_get.return_value = mock.MagicMock(status_code=200)
            r3 = client.get("/api/integrations/razorpay/status")
            assert r3.status_code == 200
            data3 = r3.json()
            assert data3["mode"] == "test"
            assert data3["configured"] is True
            assert data3["reachable"] is True
            
        # 4. Test test mode (configured but unreachable/error)
        with mock.patch("httpx.get", side_effect=Exception("Timeout")):
            r4 = client.get("/api/integrations/razorpay/status")
            assert r4.status_code == 200
            data4 = r4.json()
            assert data4["mode"] == "test"
            assert data4["configured"] is True
            assert data4["reachable"] is False
    finally:
        settings.RAZORPAY_MODE = orig_mode
        settings.RAZORPAY_KEY_ID = orig_id
        settings.RAZORPAY_KEY_SECRET = orig_secret

def test_idempotency_across_session_restart():
    import tempfile
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.database import Base
    from backend.app.models import PolicySettings, RecoveryCase, RecoveryAction
    from backend.app.services.executor import execute_recovery_action
    
    # 1. Create a temp database file to simulate application restart
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_restart.db")
    temp_db_url = f"sqlite:///{db_path}"
    
    engine = create_engine(temp_db_url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    
    # Setup initial data in DB
    db1 = Session()
    policy = PolicySettings(
        max_retries=3,
        retry_cooldown=3600,
        auto_recovery_ceiling=0.0,
        human_approval_threshold=50000.0,
        daily_action_limit=100,
        comms_enabled=True,
        hinglish_enabled=True
    )
    db1.add(policy)
    db1.commit()
    
    p = create_mock_payment(db1, "pay_restart")
    case = ingest_failed_payment(db1, p.record_id)
    key = "recovery:pay_restart:custom_restart"
    
    case_id = case.case_id
    
    # Execute Request 1
    import unittest.mock as mock
    from backend.app.integrations.payment_adapter import MockRazorpayAdapter
    
    with mock.patch.object(MockRazorpayAdapter, "retry_payment") as mock_retry:
        mock_retry.return_value = {
            "id": "pay_sim_123",
            "status": "captured",
            "amount": 100000,
            "currency": "INR",
            "simulated": True
        }
        res1 = execute_recovery_action(db1, case_id, idempotency_key=key)
        assert res1["outcome"] == "recovered"
        assert mock_retry.call_count == 1
    
    db1.close()
    
    # 2. Simulate complete restart by creating a new engine, Session, and DB connection
    engine2 = create_engine(temp_db_url)
    Session2 = sessionmaker(bind=engine2)
    db2 = Session2()
    
    # Execute Request 2 with same key
    with mock.patch.object(MockRazorpayAdapter, "retry_payment") as mock_retry2:
        # Since it is cached in the DB, it should load the cached result from DB
        # and NEVER invoke the payment adapter's retry_payment method.
        res2 = execute_recovery_action(db2, case_id, idempotency_key=key)
        assert res2["outcome"] == "recovered"
        assert res2.get("cached") is True
        assert mock_retry2.call_count == 0
        
    db2.close()
    
    # Cleanup temp file
    try:
        os.remove(db_path)
        os.rmdir(temp_dir)
    except Exception:
        pass


def test_dashboard_metric_consistency(db_session):
    # 1. Create a recovered case in Category A (bank_timeout) - non-held-out
    p1 = create_mock_payment(db_session, "pay_cons_1", amount=1000.0, failure_code="bank_timeout")
    p1.is_held_out = False
    db_session.add(p1)
    db_session.commit()
    case1 = ingest_failed_payment(db_session, p1.record_id)
    case1.status = "RECOVERED"
    p1.status = "RECOVERED"
    db_session.commit()
    
    # 2. Create a recovered case in Category B (card_expired) - non-held-out
    p2 = create_mock_payment(db_session, "pay_cons_2", amount=2000.0, failure_code="card_expired")
    p2.is_held_out = False
    db_session.add(p2)
    db_session.commit()
    case2 = ingest_failed_payment(db_session, p2.record_id)
    case2.status = "RECOVERED"
    p2.status = "RECOVERED"
    db_session.commit()
    
    # 3. Create a recovered case in Category C (network_error) - held-out (should be excluded)
    p3 = create_mock_payment(db_session, "pay_cons_3", amount=3000.0, failure_code="network_error")
    p3.is_held_out = True
    db_session.add(p3)
    db_session.commit()
    case3 = ingest_failed_payment(db_session, p3.record_id)
    case3.status = "RECOVERED"
    p3.status = "RECOVERED"
    db_session.commit()

    # 4. Create an active case in Category A (bank_timeout) - non-held-out
    p4 = create_mock_payment(db_session, "pay_cons_4", amount=60000.0, failure_code="bank_timeout")
    p4.is_held_out = False
    db_session.add(p4)
    db_session.commit()
    case4 = ingest_failed_payment(db_session, p4.record_id)
    case4.status = "APPROVED"
    db_session.commit()
    
    # Call the dashboard metrics function
    metrics = calculate_dashboard_metrics(db_session)
    
    # Assertions
    # 1. Overall recovered count must exclude held-out case3, so it should be exactly 2
    assert metrics["successful_recoveries"] == 2
    
    # Check that total cases (denominator) only includes non-held-out (case1, case2, case4) = 3 cases
    # (Note: case3 is held-out, so excluded from total_cases)
    # Recovery rate is 2 / 3 * 100 = 66.67%
    assert metrics["recovery_rate"] == 66.67
    
    # Query case categories for non-held-out to mimic frontend behavior
    payments = db_session.query(PaymentRecord).filter(PaymentRecord.is_held_out == False).all()
    
    def get_category_metrics(code):
        code_payments = [p for p in payments if p.failure_code == code]
        total = len(code_payments)
        recovered = len([p for p in code_payments if p.status in ["RECOVERED", "SUCCESS"]])
        rate = round((recovered / total * 100.0), 2) if total > 0 else 0.0
        return total, recovered, rate
        
    t_a, r_a, rate_a = get_category_metrics("bank_timeout")
    t_b, r_b, rate_b = get_category_metrics("card_expired")
    t_c, r_c, rate_c = get_category_metrics("network_error")
    
    # Assert category specific recovered counts
    assert r_a == 1  # 1 from p1 (p4 is active/APPROVED so not recovered)
    assert r_b == 1  # 1 from p2
    assert r_c == 0  # p3 is excluded because is_held_out is True
    
    # Assert reconciliation: SUM(recovered by category) == metrics["successful_recoveries"]
    total_recovered_categories = sum(
        get_category_metrics(code)[1]
        for code in ["bank_timeout", "card_expired", "network_error", "insufficient_funds", "mandate_revoked", "issuer_declined_generic", "do_not_honor"]
    )
    assert total_recovered_categories == metrics["successful_recoveries"]


