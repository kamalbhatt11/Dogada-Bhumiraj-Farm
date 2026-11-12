"""Dairy delivery, customer portal and accounting models."""
from datetime import datetime
from . import db

class DairyCustomer(db.Model):
    __tablename__ = 'dairy_customers'
    id=db.Column(db.Integer, primary_key=True)
    code=db.Column(db.String(30), unique=True, nullable=False)
    name=db.Column(db.String(120), nullable=False)
    username=db.Column(db.String(80), unique=True, nullable=False)
    password_hash=db.Column(db.String(255), nullable=False)
    phone=db.Column(db.String(40), nullable=False, default='')
    address=db.Column(db.Text, default='')
    start_date=db.Column(db.Date, nullable=False)
    status=db.Column(db.String(20), default='active', nullable=False) # active/paused/closed/archived
    pause_until=db.Column(db.Date)
    created_at=db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class DairySubscription(db.Model):
    __tablename__='dairy_subscriptions'
    id=db.Column(db.Integer, primary_key=True)
    customer_id=db.Column(db.Integer, db.ForeignKey('dairy_customers.id'), nullable=False, index=True)
    product_id=db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity=db.Column(db.Numeric(12,3), nullable=False)
    effective_from=db.Column(db.Date, nullable=False)
    effective_until=db.Column(db.Date)
    customer=db.relationship('DairyCustomer', backref='subscriptions')
    product=db.relationship('Product')

class DairyDelivery(db.Model):
    __tablename__='dairy_deliveries'
    id=db.Column(db.Integer, primary_key=True)
    customer_id=db.Column(db.Integer, db.ForeignKey('dairy_customers.id'), nullable=False, index=True)
    product_id=db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    delivery_date=db.Column(db.Date, nullable=False, index=True)
    expected_quantity=db.Column(db.Numeric(12,3), nullable=False, default=0)
    delivered_quantity=db.Column(db.Numeric(12,3), nullable=False, default=0)
    unit_price=db.Column(db.Numeric(12,2), nullable=False)
    status=db.Column(db.String(20), nullable=False, default='delivered')
    notes=db.Column(db.String(500), default='')
    created_at=db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at=db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    recorded_by=db.Column(db.String(80), default='owner')
    customer=db.relationship('DairyCustomer')
    product=db.relationship('Product')
    __table_args__=(db.UniqueConstraint('customer_id','product_id','delivery_date',name='uq_dairy_delivery_day'),)

class DairyExtraOrder(db.Model):
    __tablename__='dairy_extra_orders'
    id=db.Column(db.Integer, primary_key=True)
    customer_id=db.Column(db.Integer, db.ForeignKey('dairy_customers.id'), nullable=False, index=True)
    order_date=db.Column(db.Date, nullable=False, index=True)
    status=db.Column(db.String(20), default='delivered', nullable=False)
    notes=db.Column(db.String(500), default='')
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    customer=db.relationship('DairyCustomer')
    items=db.relationship('DairyExtraItem', backref='order', cascade='all, delete-orphan')
    @property
    def total(self):
        return sum((x.quantity*x.unit_price for x in self.items), start=0)

class DairyExtraItem(db.Model):
    __tablename__='dairy_extra_items'
    id=db.Column(db.Integer, primary_key=True)
    order_id=db.Column(db.Integer, db.ForeignKey('dairy_extra_orders.id'), nullable=False)
    product_id=db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity=db.Column(db.Numeric(12,3), nullable=False)
    unit_price=db.Column(db.Numeric(12,2), nullable=False)
    product=db.relationship('Product')

class DairyLedger(db.Model):
    __tablename__='dairy_ledger'
    id=db.Column(db.Integer, primary_key=True)
    customer_id=db.Column(db.Integer, db.ForeignKey('dairy_customers.id'), nullable=False, index=True)
    entry_date=db.Column(db.Date, nullable=False, index=True)
    kind=db.Column(db.String(20), nullable=False) # charge/payment/adjustment
    debit=db.Column(db.Numeric(12,2), nullable=False, default=0)
    credit=db.Column(db.Numeric(12,2), nullable=False, default=0)
    description=db.Column(db.String(250), nullable=False)
    source_type=db.Column(db.String(30))
    source_id=db.Column(db.Integer)
    created_at=db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    customer=db.relationship('DairyCustomer')

class DairyPayment(db.Model):
    __tablename__='dairy_payments'
    id=db.Column(db.Integer, primary_key=True)
    customer_id=db.Column(db.Integer, db.ForeignKey('dairy_customers.id'), nullable=False, index=True)
    payment_date=db.Column(db.Date, nullable=False)
    amount=db.Column(db.Numeric(12,2), nullable=False)
    method=db.Column(db.String(30), nullable=False)
    reference=db.Column(db.String(120), default='')
    note=db.Column(db.String(500), default='')
    status=db.Column(db.String(20), default='active')
    ledger_id=db.Column(db.Integer, db.ForeignKey('dairy_ledger.id'), nullable=False)
    customer=db.relationship('DairyCustomer')

class DairyAllocation(db.Model):
    __tablename__='dairy_allocations'
    id=db.Column(db.Integer, primary_key=True)
    payment_id=db.Column(db.Integer, db.ForeignKey('dairy_payments.id'), nullable=False)
    charge_ledger_id=db.Column(db.Integer, db.ForeignKey('dairy_ledger.id'), nullable=False)
    amount=db.Column(db.Numeric(12,2), nullable=False)

class DairyInvoice(db.Model):
    __tablename__='dairy_invoices'
    id=db.Column(db.Integer, primary_key=True)
    customer_id=db.Column(db.Integer, db.ForeignKey('dairy_customers.id'), nullable=False, index=True)
    start_date=db.Column(db.Date, nullable=False)
    end_date=db.Column(db.Date, nullable=False)
    issued_at=db.Column(db.DateTime, default=datetime.utcnow)
    total=db.Column(db.Numeric(12,2), nullable=False, default=0)
    status=db.Column(db.String(20), default='unpaid')
    customer=db.relationship('DairyCustomer')

class DairyAudit(db.Model):
    __tablename__='dairy_audit'
    id=db.Column(db.Integer, primary_key=True)
    actor=db.Column(db.String(100), nullable=False)
    action=db.Column(db.String(100), nullable=False)
    details=db.Column(db.Text, default='')
    created_at=db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class DairyRequest(db.Model):
    __tablename__='dairy_requests'
    id=db.Column(db.Integer, primary_key=True)
    customer_id=db.Column(db.Integer, db.ForeignKey('dairy_customers.id'), nullable=False)
    message=db.Column(db.Text, nullable=False)
    status=db.Column(db.String(20), default='pending')
    owner_reply=db.Column(db.Text, default='')
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    customer=db.relationship('DairyCustomer')


class DairyLoginAttempt(db.Model):
    """Persistent customer-login throttling keyed by an HMAC IP digest."""
    __tablename__ = 'dairy_login_attempts'
    ip_digest = db.Column(db.String(64), primary_key=True)
    failures = db.Column(db.Integer, nullable=False, default=0)
    window_started = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    locked_until = db.Column(db.DateTime)
