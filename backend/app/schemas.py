from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class CustomerSchema(BaseModel):
    customer_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    opted_out_of_comms: bool
    previous_refund_requested: bool
    previous_success_count: int
    previous_failure_count: int

    class Config:
        from_attributes = True

class OrderSchema(BaseModel):
    order_id: str
    customer_id: str
    amount: float
    currency: str
    status: str

    class Config:
        from_attributes = True

class PaymentAttemptSchema(BaseModel):
    attempt_id: str
    payment_record_id: str
    attempt_number: int
    action_type: str
    status: str
    gateway_payment_id: Optional[str] = None
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

class PaymentRecordSchema(BaseModel):
    record_id: str
    customer_id: str
    order_id: str
    type: str
    amount: float
    currency: str
    failure_code: Optional[str] = None
    failure_timestamp: datetime
    retry_count_so_far: int
    payment_method: str
    days_since_failure: int
    subscription_status: Optional[str] = None
    status: str
    customer: Optional[CustomerSchema] = None
    order: Optional[OrderSchema] = None

    class Config:
        from_attributes = True

class RecoveryActionSchema(BaseModel):
    action_id: str
    case_id: str
    action_type: str
    status: str
    idempotency_key: str
    comms_channel: Optional[str] = None
    comms_language: Optional[str] = None
    comms_content: Optional[str] = None
    executed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AIDecisionSchema(BaseModel):
    decision_id: str
    case_id: str
    classification: Optional[str] = None
    recommended_action: Optional[str] = None
    confidence: float
    reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class RecoveryCaseSchema(BaseModel):
    case_id: str
    payment_record_id: str
    status: str
    failure_classification: Optional[str] = None
    recovery_probability: float
    recommended_action: Optional[str] = None
    decision_source: Optional[str] = None
    block_reason: Optional[str] = None
    escalation_reason: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    payment: Optional[PaymentRecordSchema] = None
    actions: List[RecoveryActionSchema] = []
    ai_decisions: List[AIDecisionSchema] = []

    class Config:
        from_attributes = True

class AuditEventSchema(BaseModel):
    event_id: str
    timestamp: datetime
    record_id: Optional[str] = None
    customer_id: Optional[str] = None
    case_id: Optional[str] = None
    action: str
    actor: str
    decision_source: Optional[str] = None
    reason: Optional[str] = None
    policy_result: Optional[str] = None
    idempotency_key: Optional[str] = None
    provider_result: Optional[str] = None
    outcome: Optional[str] = None

    class Config:
        from_attributes = True

class PolicySettingsSchema(BaseModel):
    max_retries: int
    retry_cooldown: int
    auto_recovery_ceiling: float
    human_approval_threshold: float
    daily_action_limit: int
    comms_enabled: bool
    hinglish_enabled: bool

    class Config:
        from_attributes = True

class PolicyUpdateSchema(BaseModel):
    max_retries: Optional[int] = None
    retry_cooldown: Optional[int] = None
    auto_recovery_ceiling: Optional[float] = None
    human_approval_threshold: Optional[float] = None
    daily_action_limit: Optional[int] = None
    comms_enabled: Optional[bool] = None
    hinglish_enabled: Optional[bool] = None

class SimulationRequestSchema(BaseModel):
    payment_id: str
    scenario: str  # success, failure, timeout, 500, duplicate, already_completed, unknown_state

class AnalyzeRequestSchema(BaseModel):
    payment_record_ids: Optional[List[str]] = None

class BatchExecuteRequestSchema(BaseModel):
    case_ids: List[str]

class DashboardMetricsSchema(BaseModel):
    revenue_at_risk: float
    recoverable_revenue: float
    revenue_recovered: float
    recovery_rate: float
    recovery_attempts: int
    successful_recoveries: int
    guardrail_blocks: int
    human_escalations: int
    failed_recoveries: int
    unresolved_cases: int

class EvaluationRunSchema(BaseModel):
    run_id: str
    timestamp: datetime
    dataset_size: int
    held_out_size: int
    precision: float
    recall: float
    f1: float
    recovery_attempts: int
    successful_recoveries: int
    revenue_at_risk: float
    revenue_recovered: float
    guardrail_blocks: int
    human_escalations: int
    comparison_data: Optional[str] = None

    class Config:
        from_attributes = True
