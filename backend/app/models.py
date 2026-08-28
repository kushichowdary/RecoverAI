import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Customer(Base):
    __tablename__ = "customers"
    
    customer_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    opted_out_of_comms = Column(Boolean, default=False)
    previous_refund_requested = Column(Boolean, default=False)
    previous_success_count = Column(Integer, default=0)
    previous_failure_count = Column(Integer, default=0)

    # Relationships
    payments = relationship("PaymentRecord", back_populates="customer")
    orders = relationship("Order", back_populates="customer")

class Order(Base):
    __tablename__ = "orders"
    
    order_id = Column(String(50), primary_key=True)
    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    status = Column(String(50), default="pending")

    # Relationships
    customer = relationship("Customer", back_populates="orders")
    payments = relationship("PaymentRecord", back_populates="order")

class PaymentRecord(Base):
    __tablename__ = "payments"
    
    record_id = Column(String(50), primary_key=True)
    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=False)
    order_id = Column(String(50), ForeignKey("orders.order_id"), nullable=False)
    type = Column(String(50), nullable=False)  # payment, subscription_mandate
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    failure_code = Column(String(100), nullable=True)
    failure_timestamp = Column(DateTime, default=datetime.utcnow)
    retry_count_so_far = Column(Integer, default=0)
    payment_method = Column(String(50), nullable=False)  # card, upi, netbanking, wallet
    days_since_failure = Column(Integer, default=0)
    subscription_status = Column(String(50), nullable=True)
    status = Column(String(50), default="FAILED")  # FAILED, SUCCESS, RECOVERED
    is_held_out = Column(Boolean, default=False)
    
    # Ground truth (hidden from AI)
    actually_recoverable = Column(Boolean, default=False)
    best_action = Column(String(100), nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="payments")
    order = relationship("Order", back_populates="payments")
    recovery_cases = relationship("RecoveryCase", back_populates="payment")
    attempts = relationship("PaymentAttempt", back_populates="payment")

class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"
    
    attempt_id = Column(String(50), primary_key=True, default=generate_uuid)
    payment_record_id = Column(String(50), ForeignKey("payments.record_id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    action_type = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)  # PENDING, SUCCESS, FAILED, TIMEOUT
    gateway_payment_id = Column(String(50), nullable=True)
    error_code = Column(String(100), nullable=True)
    error_description = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    payment = relationship("PaymentRecord", back_populates="attempts")

class RecoveryCase(Base):
    __tablename__ = "recovery_cases"
    
    case_id = Column(String(50), primary_key=True, default=generate_uuid)
    payment_record_id = Column(String(50), ForeignKey("payments.record_id"), nullable=False)
    status = Column(String(50), default="DETECTED")
    failure_classification = Column(String(100), nullable=True)
    recovery_probability = Column(Float, default=0.0)
    recommended_action = Column(String(100), nullable=True)
    decision_source = Column(String(50), nullable=True)  # rules, ai
    block_reason = Column(String(255), nullable=True)
    escalation_reason = Column(String(255), nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    payment = relationship("PaymentRecord", back_populates="recovery_cases")
    actions = relationship("RecoveryAction", back_populates="case")
    ai_decisions = relationship("AIDecision", back_populates="case")

class RecoveryAction(Base):
    __tablename__ = "recovery_actions"
    
    action_id = Column(String(50), primary_key=True, default=generate_uuid)
    case_id = Column(String(50), ForeignKey("recovery_cases.case_id"), nullable=False)
    action_type = Column(String(100), nullable=False)
    status = Column(String(50), default="PENDING")  # PENDING, EXECUTING, SUCCESS, FAILED, BLOCKED, SKIPPED
    idempotency_key = Column(String(100), unique=True, nullable=False)
    comms_channel = Column(String(50), nullable=True)
    comms_language = Column(String(50), nullable=True)
    comms_content = Column(Text, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    response_payload = Column(Text, nullable=True)  # JSON dump of provider response

    # Relationships
    case = relationship("RecoveryCase", back_populates="actions")

class AIDecision(Base):
    __tablename__ = "ai_decisions"
    
    decision_id = Column(String(50), primary_key=True, default=generate_uuid)
    case_id = Column(String(50), ForeignKey("recovery_cases.case_id"), nullable=False)
    prompt = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)
    classification = Column(String(100), nullable=True)
    recommended_action = Column(String(100), nullable=True)
    confidence = Column(Float, default=0.0)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    case = relationship("RecoveryCase", back_populates="ai_decisions")

class PolicySettings(Base):
    __tablename__ = "policies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    max_retries = Column(Integer, default=3)
    retry_cooldown = Column(Integer, default=3600)  # in seconds
    auto_recovery_ceiling = Column(Float, default=50000.0)
    human_approval_threshold = Column(Float, default=50000.0)
    daily_action_limit = Column(Integer, default=100)
    comms_enabled = Column(Boolean, default=True)
    hinglish_enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    event_id = Column(String(50), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow)
    record_id = Column(String(50), nullable=True)
    customer_id = Column(String(50), nullable=True)
    case_id = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)
    actor = Column(String(100), default="system")
    decision_source = Column(String(50), nullable=True)
    reason = Column(Text, nullable=True)
    policy_result = Column(String(100), nullable=True)
    idempotency_key = Column(String(100), nullable=True)
    provider_result = Column(Text, nullable=True)
    outcome = Column(String(100), nullable=True)

class Notification(Base):
    __tablename__ = "notifications"
    
    notification_id = Column(String(50), primary_key=True, default=generate_uuid)
    customer_id = Column(String(50), ForeignKey("customers.customer_id"), nullable=False)
    case_id = Column(String(50), ForeignKey("recovery_cases.case_id"), nullable=False)
    channel = Column(String(50), nullable=False)
    language = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(50), default="SENT")  # SENT, FAILED, BLOCKED
    sent_at = Column(DateTime, default=datetime.utcnow)

class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    
    run_id = Column(String(50), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow)
    dataset_size = Column(Integer, default=0)
    held_out_size = Column(Integer, default=0)
    precision = Column(Float, default=0.0)
    recall = Column(Float, default=0.0)
    f1 = Column(Float, default=0.0)
    recovery_attempts = Column(Integer, default=0)
    successful_recoveries = Column(Integer, default=0)
    revenue_at_risk = Column(Float, default=0.0)
    revenue_recovered = Column(Float, default=0.0)
    guardrail_blocks = Column(Integer, default=0)
    human_escalations = Column(Integer, default=0)
    comparison_data = Column(Text, nullable=True)  # JSON-serialized comparison
