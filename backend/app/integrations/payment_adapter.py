import time
import logging
import random
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import httpx
from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.models import PaymentRecord

logger = logging.getLogger("recoverai")

class PaymentProvider(ABC):
    @abstractmethod
    def fetch_payment(self, payment_id: str, db: Optional[Any] = None) -> Dict[str, Any]:
        """
        Retrieves the details and status of a payment transaction from the gateway.
        """
        pass

    @abstractmethod
    def fetch_order_payments(self, order_id: str, db: Optional[Any] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all payments associated with an order ID.
        """
        pass

    @abstractmethod
    def capture_payment(self, payment_id: str, amount: float) -> Dict[str, Any]:
        """
        Captures an authorized payment of a specified amount.
        """
        pass

    @abstractmethod
    def verify_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Verifies the final payment status.
        """
        pass

class MockRazorpayAdapter(PaymentProvider):
    # Class-level store for simulated scenarios and idempotency cache
    _scenario_overrides: Dict[str, str] = {}
    _idempotency_cache: Dict[str, Dict[str, Any]] = {}
    _payment_states: Dict[str, str] = {}  # Tracks payment states: captured, failed, etc.

    @classmethod
    def set_scenario_override(cls, payment_id: str, scenario: str):
        cls._scenario_overrides[payment_id] = scenario
        
    @classmethod
    def clear_overrides(cls):
        cls._scenario_overrides.clear()
        cls._payment_states.clear()
        cls._idempotency_cache.clear()

    def fetch_payment(self, payment_id: str, db: Optional[Any] = None) -> Dict[str, Any]:
        # Return state of the simulated payment
        state = self._payment_states.get(payment_id, "failed")
        amount = 50000.0
        currency = "INR"
        method = "card"
        
        local_db = db
        is_local = False
        if local_db is None:
            local_db = SessionLocal()
            is_local = True
            
        try:
            p = local_db.query(PaymentRecord).filter(PaymentRecord.record_id == payment_id).first()
            if p:
                amount = p.amount
                currency = p.currency
                method = p.payment_method
                if p.status in ["RECOVERED", "SUCCESS"]:
                    state = "captured"
        finally:
            if is_local and local_db:
                local_db.close()

        if state in ["recovered", "success"]:
            state = "captured"

        return {
            "id": payment_id,
            "status": state,
            "amount": int(amount * 100),
            "currency": currency,
            "method": method,
            "error_code": None if state == "captured" else "bad_credentials",
            "error_description": None if state == "captured" else "Payment failed"
        }

    def fetch_order_payments(self, order_id: str, db: Optional[Any] = None) -> List[Dict[str, Any]]:
        local_db = db
        is_local = False
        if local_db is None:
            local_db = SessionLocal()
            is_local = True
        try:
            payments = local_db.query(PaymentRecord).filter(PaymentRecord.order_id == order_id).all()
            results = []
            for p in payments:
                state = self._payment_states.get(p.record_id, p.status.lower())
                if state in ["recovered", "success", "captured"]:
                    state = "captured"
                elif state == "failed":
                    state = "failed"
                results.append({
                    "id": p.record_id,
                    "status": state,
                    "amount": int(p.amount * 100),
                    "currency": p.currency,
                    "method": p.payment_method,
                    "order_id": order_id
                })
            return results
        finally:
            if is_local and local_db:
                local_db.close()

    def capture_payment(self, payment_id: str, amount: float) -> Dict[str, Any]:
        self._payment_states[payment_id] = "captured"
        response = {
            "id": payment_id,
            "status": "captured",
            "amount": int(amount * 100),
            "currency": "INR",
            "simulated": True
        }
        return response

    def verify_payment(self, payment_id: str) -> Dict[str, Any]:
        state = self._payment_states.get(payment_id, "failed")
        if state in ["recovered", "success", "captured"]:
            state = "captured"
        else:
            state = "failed"
        return {
            "id": payment_id,
            "status": state,
            "verified": True
        }

    def retry_payment(self, payment_id: str, amount: float, idempotency_key: str, scenario: Optional[str] = None) -> Dict[str, Any]:
        # Check idempotency first
        if idempotency_key in self._idempotency_cache:
            logger.info(f"[IDEMPOTENCY] Key {idempotency_key} already exists in cache. Returning cached result.")
            return self._idempotency_cache[idempotency_key]

        # Determine scenario
        selected_scenario = scenario or self._scenario_overrides.get(payment_id, "success")
        logger.info(f"[SIMULATOR] Executing retry for payment {payment_id} with scenario: {selected_scenario}")
        
        # Simulated responses
        if selected_scenario == "success":
            response = {
                "id": f"pay_sim_{random.randint(100000, 999999)}",
                "status": "captured",
                "amount": int(amount * 100),  # Razorpay amounts are in paise
                "currency": "INR",
                "error_code": None,
                "error_description": None,
                "simulated": True,
                "scenario": "success"
            }
            self._payment_states[payment_id] = "captured"
            self._idempotency_cache[idempotency_key] = response
            return response
            
        elif selected_scenario == "failed_retry":
            response = {
                "id": f"pay_sim_{random.randint(100000, 999999)}",
                "status": "failed",
                "amount": int(amount * 100),
                "currency": "INR",
                "error_code": "insufficient_funds",
                "error_description": "The customer has insufficient funds in their account.",
                "simulated": True,
                "scenario": "failed_retry"
            }
            self._payment_states[payment_id] = "failed"
            self._idempotency_cache[idempotency_key] = response
            return response
            
        elif selected_scenario == "timeout":
            # Simulate a gateway timeout
            logger.warning(f"[SIMULATOR] Simulating read timeout for payment {payment_id}")
            time.sleep(0.5)
            raise httpx.ReadTimeout("Simulated gateway read timeout")
            
        elif selected_scenario == "500":
            # Simulate HTTP 500
            logger.error(f"[SIMULATOR] Simulating HTTP 500 error for payment {payment_id}")
            raise httpx.HTTPStatusError(
                "Internal Server Error",
                request=httpx.Request("POST", "https://api.razorpay.com/v1/payments/retry"),
                response=httpx.Response(500, text="Internal Server Error")
            )
            
        elif selected_scenario == "duplicate":
            response = {
                "id": f"pay_sim_dup_{random.randint(100000, 999999)}",
                "status": "failed",
                "error_code": "duplicate_transaction",
                "error_description": "A transaction with this order ID already succeeded.",
                "simulated": True,
                "scenario": "duplicate"
            }
            self._idempotency_cache[idempotency_key] = response
            return response
            
        elif selected_scenario == "payment_already_completed":
            response = {
                "id": payment_id,
                "status": "captured",
                "amount": int(amount * 100),
                "currency": "INR",
                "error_code": None,
                "error_description": None,
                "simulated": True,
                "scenario": "payment_already_completed"
            }
            self._payment_states[payment_id] = "captured"
            self._idempotency_cache[idempotency_key] = response
            return response
            
        elif selected_scenario == "unknown_payment_state":
            response = {
                "id": payment_id,
                "status": "unknown",
                "amount": int(amount * 100),
                "currency": "INR",
                "error_code": "unknown_state",
                "error_description": "The transaction state is currently unknown at the gateway.",
                "simulated": True,
                "scenario": "unknown_payment_state"
            }
            self._payment_states[payment_id] = "unknown"
            self._idempotency_cache[idempotency_key] = response
            return response

        # Default fallback
        response = {
            "id": f"pay_sim_{random.randint(100000, 999999)}",
            "status": "captured",
            "amount": int(amount * 100),
            "currency": "INR",
            "simulated": True
        }
        self._payment_states[payment_id] = "captured"
        return response

class RazorpayTestAdapter(PaymentProvider):
    def __init__(self):
        self.base_url = "https://api.razorpay.com/v1"
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        
        if not self.key_id or not self.key_secret:
            raise ValueError(
                "Missing Razorpay credentials. Razorpay test mode requires RAZORPAY_KEY_ID "
                "and RAZORPAY_KEY_SECRET to be configured in .env."
            )
        self.auth = (self.key_id, self.key_secret)

    def fetch_payment(self, payment_id: str, db: Optional[Any] = None) -> Dict[str, Any]:
        logger.info(f"[Razorpay API] Fetching payment details for {payment_id}")
        try:
            with httpx.Client(auth=self.auth) as client:
                resp = client.get(f"{self.base_url}/payments/{payment_id}")
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [400, 404]:
                logger.warning(f"Payment ID {payment_id} not found or invalid format on Razorpay server: {e}")
                return {
                    "id": payment_id,
                    "status": "not_found",
                    "error_code": "invalid_payment_id",
                    "error_description": f"Payment ID {payment_id} was not found on Razorpay gateway. If using synthetic demo data, switch RAZORPAY_MODE=mock."
                }
            raise


    def fetch_order_payments(self, order_id: str, db: Optional[Any] = None) -> List[Dict[str, Any]]:
        logger.info(f"[Razorpay API] Fetching payments for order {order_id}")
        with httpx.Client(auth=self.auth) as client:
            resp = client.get(f"{self.base_url}/orders/{order_id}/payments")
            resp.raise_for_status()
            data = resp.json()
            return data.get("items", [])

    def capture_payment(self, payment_id: str, amount: float) -> Dict[str, Any]:
        logger.info(f"[Razorpay API] Capturing payment {payment_id} for amount {amount}")
        payload = {
            "amount": int(amount * 100),
            "currency": "INR"
        }
            
        with httpx.Client(auth=self.auth) as client:
            resp = client.post(
                f"{self.base_url}/payments/{payment_id}/capture",
                json=payload
            )
            resp.raise_for_status()
            return resp.json()

    def verify_payment(self, payment_id: str) -> Dict[str, Any]:
        logger.info(f"[Razorpay API] Verifying payment {payment_id}")
        details = self.fetch_payment(payment_id)
        return {
            "id": payment_id,
            "status": details.get("status"),
            "verified": True
        }

def get_payment_adapter() -> PaymentProvider:
    if settings.RAZORPAY_MODE == "test":
        return RazorpayTestAdapter()
    return MockRazorpayAdapter()
