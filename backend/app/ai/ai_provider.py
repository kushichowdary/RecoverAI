import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from backend.app.config import settings

logger = logging.getLogger("recoverai")

class AIRecommendation(BaseModel):
    classification: Literal["recoverable", "unrecoverable"]
    recommended_action: Literal[
        "retry_payment",
        "schedule_retry",
        "send_payment_reminder",
        "request_payment_method_update",
        "request_mandate_reauthorization",
        "escalate_to_human",
        "no_action"
    ]
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reason: str = Field(description="Reason for recommending this action")

    model_config = {
        "extra": "forbid"
    }

class AIProvider(ABC):
    @abstractmethod
    def recommend_recovery(self, payment_info: Dict[str, Any]) -> AIRecommendation:
        pass

    @abstractmethod
    def generate_communication(self, comm_info: Dict[str, Any]) -> str:
        pass

class MockAIProvider(AIProvider):
    def recommend_recovery(self, payment_info: Dict[str, Any]) -> AIRecommendation:
        # Mimic intelligent decision based on previous history
        success_count = payment_info.get("previous_success_count", 0)
        failure_count = payment_info.get("previous_failure_count", 0)
        retry_count = payment_info.get("retry_count_so_far", 0)
        failure_code = payment_info.get("failure_code", "")
        amount = payment_info.get("amount", 0.0)
        
        # Ground truth/mock logic
        if success_count >= 5 and retry_count < 3:
            classification = "recoverable"
            recommended_action = "retry_payment"
            confidence = 0.85
            reason = f"Customer has a high prior success count of {success_count} and retry attempts {retry_count} are below limit."
        elif success_count > 0 and retry_count < 3:
            classification = "recoverable"
            recommended_action = "send_payment_reminder"
            confidence = 0.75
            reason = f"Customer has active payment history. Recommending reminder before automatic retry."
        else:
            classification = "unrecoverable"
            recommended_action = "escalate_to_human"
            confidence = 0.80
            reason = "No prior success history found for customer, or retry limit reached."
            
        return AIRecommendation(
            classification=classification,
            recommended_action=recommended_action,
            confidence=confidence,
            reason=reason
        )
        
    def generate_communication(self, comm_info: Dict[str, Any]) -> str:
        name = comm_info.get("customer_name", "Customer")
        amount = comm_info.get("amount", 0.0)
        reason = comm_info.get("failure_reason", "technical issue")
        language = comm_info.get("language", "english").lower()
        tone = comm_info.get("merchant_tone", "polite").lower()
        
        if language == "hinglish":
            if tone == "urgent":
                return f"Hey {name}! Aapka Rs. {amount} ka payment '{reason}' ki wajah se fail ho gaya hai. Please turant niche diye link se pay karein taaki services suspend na ho."
            return f"Hello {name}, aapka Rs. {amount} ka payment fail ho gaya hai. Reason: {reason}. Niche diye link se payment update kar sakte hain. Thank you!"
        else:
            if tone == "urgent":
                return f"Urgent: Dear {name}, your payment of INR {amount} has failed due to '{reason}'. Please complete the payment immediately to avoid service interruption."
            return f"Dear {name}, we noticed your payment of INR {amount} failed due to '{reason}'. You can easily complete your payment by clicking here. Thank you for your support."

class AnthropicAIProvider(AIProvider):
    def __init__(self):
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}. Falling back to mock.")
            self.client = None

    def recommend_recovery(self, payment_info: Dict[str, Any]) -> AIRecommendation:
        if not self.client:
            logger.warning("Anthropic client not configured. Falling back to MockAIProvider.")
            return MockAIProvider().recommend_recovery(payment_info)
            
        prompt = f"""You are the AI engine of RecoverAI, a failed-payment recovery agent.
Analyze the following failed payment context and output a JSON object containing the recovery classification and recommended action.

Payment Context:
{json.dumps(payment_info, indent=2)}

Output Schema:
Return ONLY a valid JSON block conforming to the following structure:
{{
  "classification": "recoverable" | "unrecoverable",
  "recommended_action": "retry_payment" | "schedule_retry" | "send_payment_reminder" | "request_payment_method_update" | "request_mandate_reauthorization" | "escalate_to_human" | "no_action",
  "confidence": float (between 0.0 and 1.0),
  "reason": "short explanation of evidence"
}}
"""
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                temperature=0.0,
                system="You are an expert payment recovery risk engine. You must output JSON conforming to the requested schema. Do not output anything else.",
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text.strip()
            data = json.loads(content)
            
            # Basic validation
            allowed_actions = {
                "retry_payment", "schedule_retry", "send_payment_reminder",
                "request_payment_method_update", "request_mandate_reauthorization",
                "escalate_to_human", "no_action"
            }
            if data.get("recommended_action") not in allowed_actions:
                raise ValueError(f"Invalid recommended action: {data.get('recommended_action')}")
                
            return AIRecommendation(**data)
            
        except Exception as e:
            logger.error(f"Anthropic recommendation request failed: {e}. Falling back to mock.")
            return MockAIProvider().recommend_recovery(payment_info)

    def generate_communication(self, comm_info: Dict[str, Any]) -> str:
        if not self.client:
            logger.warning("Anthropic client not configured. Falling back to MockAIProvider.")
            return MockAIProvider().generate_communication(comm_info)
            
        prompt = f"""You are the AI engine of RecoverAI.
Generate a customer communication message for a failed payment.

Communication context:
{json.dumps(comm_info, indent=2)}

Requirements:
- Target Language: {comm_info.get('language', 'english')}
- Tone: {comm_info.get('merchant_tone', 'polite')}
- Keep it concise, helpful, and clear.
- Do NOT include any sensitive payment numbers (e.g. card numbers).
- Output ONLY the message body. Do not include subject lines, greetings, placeholders, or surrounding formatting.
"""
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Anthropic communication request failed: {e}. Falling back to mock.")
            return MockAIProvider().generate_communication(comm_info)

def get_ai_provider() -> AIProvider:
    if settings.AI_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
        return AnthropicAIProvider()
    return MockAIProvider()
