import os
import sys
import random
import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to python path to import models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import Base, engine, SessionLocal
from backend.app.models import Customer, Order, PaymentRecord, PolicySettings

def generate_synthetic_data():
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Check if database is already seeded
    if db.query(PaymentRecord).count() >= 1000:
        print("Database already seeded with 1000+ records.")
        db.close()
        return

    print("Generating synthetic data...")
    random.seed(42)
    
    # 1. Generate Policy Settings
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

    # 2. Generate Customers
    customers = []
    # Generate 150 unique customers
    for i in range(150):
        cust_id = f"cust_{1000 + i}"
        name = f"Customer {i+1}"
        email = f"customer_{i+1}@example.com"
        phone = f"+9198765{i:05d}"
        
        # Realistic attributes
        opted_out_of_comms = random.random() < 0.15  # 15% opt-out
        previous_refund_requested = random.random() < 0.08  # 8% refund requested
        
        # History
        previous_success_count = random.randint(0, 15)
        if previous_success_count > 0:
            previous_failure_count = random.randint(0, 3)
        else:
            previous_failure_count = random.randint(1, 5)

        cust = Customer(
            customer_id=cust_id,
            name=name,
            email=email,
            phone=phone,
            opted_out_of_comms=opted_out_of_comms,
            previous_refund_requested=previous_refund_requested,
            previous_success_count=previous_success_count,
            previous_failure_count=previous_failure_count
        )
        db.add(cust)
        customers.append(cust)
    db.commit()

    # 3. Generate Orders and Payments
    payment_methods = ["card", "upi", "netbanking", "wallet"]
    failure_codes = [
        "insufficient_funds",
        "card_expired",
        "bank_timeout",
        "network_error",
        "mandate_revoked",
        "issuer_declined_generic",
        "do_not_honor"
    ]
    
    payment_records = []
    total_records = 1000
    
    # We want 5 duplicates, so we'll generate 995 distinct records and duplicate 5 of them.
    distinct_count = total_records - 5
    
    now = datetime.utcnow()
    
    for i in range(distinct_count):
        rec_id = f"pay_{10000 + i}"
        cust = random.choice(customers)
        
        # Order amount
        # Make a few high-value ones (>50k INR)
        if random.random() < 0.04:
            amount = float(random.randint(55000, 120000))
        else:
            amount = float(random.randint(100, 15000))
            
        order_id = f"order_{20000 + i}"
        order = Order(
            order_id=order_id,
            customer_id=cust.customer_id,
            amount=amount,
            currency="INR",
            status="pending"
        )
        db.add(order)
        
        # Failure type
        pay_type = "payment"
        fail_code = random.choices(
            failure_codes, 
            weights=[35, 15, 15, 15, 10, 5, 5], 
            k=1
        )[0]
        
        # Adjust type for mandate_revoked
        if fail_code == "mandate_revoked":
            pay_type = "subscription_mandate"
        elif random.random() < 0.20:
            pay_type = "subscription_mandate"
            
        # Retry count
        retry_count = random.randint(0, 4)
        
        # Days since failure
        days_since = random.randint(0, 30)
        fail_time = now - timedelta(days=days_since, hours=random.randint(0, 23), minutes=random.randint(0, 59))
        
        # Payment method
        pay_method = random.choice(payment_methods)
        if fail_code == "card_expired":
            pay_method = "card"
            
        sub_status = "active" if pay_type == "subscription_mandate" else None
        
        # Ground truth recovery determination
        # Insufficient funds: recoverable if history is good, retry limit not exceeded, and not opted out/refunded
        actually_recoverable = False
        best_action = "no_action"
        
        if fail_code == "insufficient_funds":
            if cust.previous_success_count > 0 and retry_count < 3 and not cust.previous_refund_requested:
                actually_recoverable = True
                best_action = "retry_payment"
            else:
                best_action = "send_payment_reminder"
        elif fail_code == "card_expired":
            actually_recoverable = True
            best_action = "request_payment_method_update"
        elif fail_code in ["bank_timeout", "network_error"]:
            if retry_count < 3:
                actually_recoverable = True
                best_action = "retry_payment"
            else:
                actually_recoverable = False
                best_action = "escalate_to_human"
        elif fail_code == "mandate_revoked":
            actually_recoverable = True
            best_action = "request_mandate_reauthorization"
        elif fail_code in ["issuer_declined_generic", "do_not_honor"]:
            # Ambiguous failures: recoverable if customer has very good history
            if cust.previous_success_count >= 5 and retry_count < 3 and not cust.previous_refund_requested:
                actually_recoverable = True
                best_action = "retry_payment"
            elif cust.previous_success_count > 0:
                actually_recoverable = False
                best_action = "send_payment_reminder"
            else:
                actually_recoverable = False
                best_action = "escalate_to_human"
                
        # If opted out of comms, best action can't be communication.
        if cust.opted_out_of_comms and best_action in ["send_payment_reminder", "request_payment_method_update", "request_mandate_reauthorization"]:
            actually_recoverable = False
            best_action = "escalate_to_human"
            
        # Refund requested block
        if cust.previous_refund_requested and best_action not in ["no_action", "escalate_to_human"]:
            actually_recoverable = False
            best_action = "no_action"
            
        # High value block
        if amount > 50000.0 and best_action not in ["no_action", "escalate_to_human"]:
            # High value requires human approval, so we can't auto-recover
            actually_recoverable = False
            best_action = "escalate_to_human"

        pay = PaymentRecord(
            record_id=rec_id,
            customer_id=cust.customer_id,
            order_id=order_id,
            type=pay_type,
            amount=amount,
            currency="INR",
            failure_code=fail_code,
            failure_timestamp=fail_time,
            retry_count_so_far=retry_count,
            payment_method=pay_method,
            days_since_failure=days_since,
            subscription_status=sub_status,
            status="FAILED",
            actually_recoverable=actually_recoverable,
            best_action=best_action,
            is_held_out=False
        )
        db.add(pay)
        payment_records.append(pay)

    db.commit()

    # 4. Generate 5 duplicates/near-duplicates
    # We will pick 5 records and insert duplicate attempts shortly after.
    dup_records = random.sample(payment_records, 5)
    for idx, orig in enumerate(dup_records):
        dup_id = f"{orig.record_id}_dup"
        # Duplicate is created 1 minute after the original failure
        dup_time = orig.failure_timestamp + timedelta(minutes=1)
        
        dup_pay = PaymentRecord(
            record_id=dup_id,
            customer_id=orig.customer_id,
            order_id=orig.order_id,
            type=orig.type,
            amount=orig.amount,
            currency=orig.currency,
            failure_code=orig.failure_code,
            failure_timestamp=dup_time,
            retry_count_so_far=orig.retry_count_so_far,
            payment_method=orig.payment_method,
            days_since_failure=orig.days_since_failure,
            subscription_status=orig.subscription_status,
            status="FAILED",
            actually_recoverable=False,  # Duplicate shouldn't be processed as a separate recoverable case
            best_action="no_action",
            is_held_out=orig.is_held_out
        )
        db.add(dup_pay)
        
    db.commit()

    # 5. Split 80% dev, 20% held-out
    # We query all payments (excluding duplicates) and mark 20% of them as held-out.
    all_non_dup_payments = db.query(PaymentRecord).filter(~PaymentRecord.record_id.like("%_dup")).all()
    # Randomly shuffle and mark 200 of them as is_held_out
    random.shuffle(all_non_dup_payments)
    held_out_count = int(total_records * 0.20)  # 200
    
    for i in range(held_out_count):
        all_non_dup_payments[i].is_held_out = True
        
    db.commit()

    print(f"Dataset generated. Total payments: {db.query(PaymentRecord).count()}")
    db.close()

if __name__ == "__main__":
    generate_synthetic_data()
