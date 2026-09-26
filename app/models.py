from flask_login import UserMixin
from . import db,login_manager
class Admin(UserMixin,db.Model):
    id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(80),unique=True,nullable=False); password_hash=db.Column(db.String(255),nullable=False)
class Product(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120),nullable=False); slug=db.Column(db.String(120),unique=True,nullable=False); price=db.Column(db.Float); unit=db.Column(db.String(50),nullable=False); category=db.Column(db.String(50),default="Dairy"); description=db.Column(db.Text,nullable=False); icon=db.Column(db.String(10),default="🥛"); active=db.Column(db.Boolean,default=True)
class Order(db.Model):
    id=db.Column(db.Integer,primary_key=True); order_code=db.Column(db.String(30),unique=True,nullable=False); customer_name=db.Column(db.String(120),nullable=False); phone=db.Column(db.String(40),nullable=False); email=db.Column(db.String(160)); address=db.Column(db.Text,nullable=False); area=db.Column(db.String(80),nullable=False); items_json=db.Column(db.Text,nullable=False); subtotal=db.Column(db.Float,nullable=False); delivery_charge=db.Column(db.Float,default=0); total=db.Column(db.Float,nullable=False); notes=db.Column(db.Text); status=db.Column(db.String(40),default="New"); payment_method=db.Column(db.String(40),default="Cash on Delivery"); created_at=db.Column(db.DateTime,server_default=db.func.now())
class Inquiry(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120),nullable=False); phone=db.Column(db.String(40),nullable=False); email=db.Column(db.String(160)); message=db.Column(db.Text,nullable=False); created_at=db.Column(db.DateTime,server_default=db.func.now()); status=db.Column(db.String(30),default="New")
@login_manager.user_loader
def load_user(uid): return Admin.query.get(int(uid))


class Animal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.String(40), unique=True, nullable=False)
    animal_type = db.Column(db.String(20), nullable=False)
    breed = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    age_years = db.Column(db.Float, nullable=False, default=0)
    color = db.Column(db.String(80), default='')
    health_status = db.Column(db.String(120), default='Healthy')
    milk_liters = db.Column(db.Float)
    price = db.Column(db.Float)
    status = db.Column(db.String(30), nullable=False, default='Available')
    photo = db.Column(db.String(150))
    description = db.Column(db.Text, default='')
    vaccinations = db.relationship('Vaccination', back_populates='animal', cascade='all, delete-orphan', order_by='Vaccination.date_given.desc()')

class Vaccination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animal.id'), nullable=False, index=True)
    vaccine_name = db.Column(db.String(150), nullable=False)
    purpose = db.Column(db.String(150), default='')
    date_given = db.Column(db.Date, nullable=False)
    next_due = db.Column(db.Date)
    notes = db.Column(db.Text, default='')
    animal = db.relationship('Animal', back_populates='vaccinations')
