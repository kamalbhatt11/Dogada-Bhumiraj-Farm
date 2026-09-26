from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from . import db
from .models import Product, Order, Inquiry, Admin, Animal, Vaccination
import json
import uuid
import math
import requests
from datetime import date, datetime, timedelta
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app, abort
from sqlalchemy import or_
import secrets

main = Blueprint('main', __name__)
admin = Blueprint('admin', __name__)

# Verify these coordinates point to your farm's actual delivery starting point.
FARM_LAT = 28.756394
FARM_LNG = 80.574151
# Public OSRM demo is for testing, not guaranteed for a production shop.
OSRM_URL = 'https://router.project-osrm.org/route/v1/driving'


def valid_coordinates(lat, lng):
    return math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180


def delivery_fee(distance_km):
    # First kilometre free; each STARTED kilometre after that costs Rs. 30.
    return max(0, math.ceil(max(0, distance_km - 1) - 1e-9)) * 30


def road_distance_km(lat, lng):
    if not valid_coordinates(lat, lng):
        raise ValueError('Invalid delivery coordinates')
    url = f'{OSRM_URL}/{FARM_LNG},{FARM_LAT};{lng},{lat}'
    response = requests.get(url, params={'overview': 'false'}, timeout=12)
    response.raise_for_status()
    data = response.json()
    if data.get('code') != 'Ok' or not data.get('routes'):
        raise ValueError('No driving route available')
    metres = data['routes'][0]['distance']
    if not isinstance(metres, (int, float)) or not math.isfinite(metres) or metres < 0:
        raise ValueError('Invalid route distance')
    return metres / 1000
@main.get('/')
def home():
    return render_template('index.html', products=Product.query.filter_by(active=True).all())


@main.get('/shop')
def shop():
    return redirect(url_for('main.products'))


@main.get('/products')
def products():
    return render_template('products.html', products=Product.query.filter_by(active=True).all())


@main.get('/livestock')
def livestock():
    return render_template('livestock.html', animals=Animal.query.filter_by(status='Available').order_by(Animal.animal_type, Animal.id.desc()).all())


@main.get('/about')
def about():
    return render_template('about.html')


@main.get('/contact')
def contact():
    return render_template('contact.html')


@main.get('/checkout')
def checkout():
    return render_template('checkout.html', farm_lat=FARM_LAT, farm_lng=FARM_LNG)

@main.get('/calculate-delivery')
def calculate_delivery():
    try:
        lat = float(request.args['lat'])
        lng = float(request.args['lng'])
        distance = road_distance_km(lat, lng)
        return jsonify(success=True, distance_km=round(distance, 3), fee=delivery_fee(distance))
    except (KeyError, ValueError, TypeError):
        return jsonify(success=False, error='Please choose a valid delivery location.'), 400
    except requests.RequestException:
        return jsonify(success=False, error='Routing service is unavailable. Please try again.'), 503


@main.post('/order')
def place_order():
    try:
        cart = json.loads(request.form.get('cart_json', '{}'))
        if not isinstance(cart, dict):
            cart = {}
    except (ValueError, TypeError):
        cart = {}

    name = request.form.get('customer_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()
    notes = request.form.get('notes', '').strip()
    payment = request.form.get('payment_method', 'Cash on Delivery')
    allowed_payments = {'Cash on Delivery', 'eSewa', 'Bank Transfer', 'Khalti'}
    if payment not in allowed_payments:
        flash('Please select a valid payment method.', 'error')
        return redirect(url_for('main.checkout'))
    if not name or not phone or not address or not cart:
        flash('Please complete your details and add products.', 'error')
        return redirect(url_for('main.checkout'))

    try:
        lat = float(request.form['customer_lat'])
        lng = float(request.form['customer_lng'])
        distance = road_distance_km(lat, lng)
        fee = delivery_fee(distance)
    except (KeyError, ValueError, TypeError):
        flash('Please select a valid delivery location.', 'error')
        return redirect(url_for('main.checkout'))
    except requests.RequestException:
        flash('Could not check driving distance. Please try again.', 'error')
        return redirect(url_for('main.checkout'))

    ids = [int(k) for k in cart if str(k).isdigit()]
    ps = Product.query.filter(Product.id.in_(ids), Product.active == True).all()
    by = {str(p.id): p for p in ps}
    items = []
    subtotal = 0
    for k, q in cart.items():
        if k not in by:
            continue
        try:
            q = int(q)
        except (TypeError, ValueError):
            continue
        p = by[k]
        if q < 1 or q > 100 or p.price is None:
            continue
        line = p.price * q
        subtotal += line
        items.append({'id': p.id, 'name': p.name, 'qty': q, 'unit': p.unit,
                      'price': p.price, 'line': line})
    if not items:
        flash('Add at least one priced product.', 'error')
        return redirect(url_for('main.products'))

    code = 'SD-' + uuid.uuid4().hex[:8].upper()
    # Existing Order model has no latitude/longitude columns; preserve the
    # selected coordinates and road distance in the existing address field.
    delivery_address = (f'{address} | Map: {lat:.6f},{lng:.6f} '
                        f'| Driving distance: {distance:.2f} km')
    order = Order(order_code=code, customer_name=name, phone=phone, email=email,
                  address=delivery_address, area='Customer-selected location',
                  items_json=json.dumps(items), subtotal=subtotal,
                  delivery_charge=fee, total=subtotal + fee, notes=notes,
                  payment_method=payment)
    db.session.add(order)
    db.session.commit()
    flash(f'Order {code} received successfully.', 'success')
    return redirect(url_for('main.success', code=code))


@main.get('/order-success/<code>')
def success(code):
    return render_template('order_success.html', order=Order.query.filter_by(order_code=code).first_or_404())


@main.post('/inquiry')
def inquiry():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    msg = request.form.get('message', '').strip()
    if not name or not phone or not msg:
        flash('Please complete the required fields.', 'error')
        return redirect(url_for('main.contact'))
    db.session.add(Inquiry(name=name, phone=phone, email=email, message=msg))
    db.session.commit()
    flash('Your message has been sent.', 'success')
    return redirect(url_for('main.contact'))


@admin.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        user = Admin.query.filter_by(username=request.form.get('username', '')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password', '')):
            login_user(user)
            return redirect(url_for('admin.dashboard'))
        flash('Invalid owner login.', 'error')
    return render_template('owner_login.html')


@admin.get('/dashboard')
@login_required
def dashboard():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    inquiries = Inquiry.query.order_by(Inquiry.created_at.desc()).all()
    products = Product.query.order_by(Product.category, Product.id).all()
    sales = sum(o.total for o in orders if o.status == 'Delivered')
    pending = sum(1 for o in orders if o.status not in ['Delivered', 'Cancelled'])
    animals = Animal.query.order_by(Animal.id.desc()).all()
    today = date.today()
    upcoming = Vaccination.query.filter(Vaccination.next_due != None, Vaccination.next_due <= today + timedelta(days=30)).order_by(Vaccination.next_due).all()
    return render_template('dashboard.html', orders=orders, inquiries=inquiries,
                           products=products, sales=sales, pending=pending,
                           animals=animals, upcoming=upcoming)


@admin.get('/orders')
@login_required
def orders():
    selected = request.args.get('status', 'All')
    statuses = ['All', 'New', 'Confirmed', 'Preparing', 'Out for Delivery', 'Delivered', 'Cancelled']
    if selected not in statuses:
        selected = 'All'
    query = Order.query
    if selected != 'All':
        query = query.filter_by(status=selected)
    all_orders = Order.query.all()
    return render_template('orders_admin.html', orders=query.order_by(Order.created_at.desc()).all(),
                           selected=selected, statuses=statuses,
                           counts={status: sum(1 for order in all_orders if status == 'All' or order.status == status) for status in statuses})


@admin.post('/order/<int:id>/status')
@login_required
def order_status(id):
    order = Order.query.get_or_404(id)
    status = request.form.get('status')
    allowed = ['New', 'Confirmed', 'Preparing', 'Out for Delivery', 'Delivered', 'Cancelled']
    if status in allowed:
        order.status = status
        db.session.commit()
    return redirect(url_for('admin.orders', status=request.form.get('filter_status', 'All')))


@admin.post('/product/<int:id>/save')
@login_required
def product_save(id):
    product = Product.query.get_or_404(id)
    product.name = request.form.get('name', product.name)
    product.unit = request.form.get('unit', product.unit)
    product.description = request.form.get('description', product.description)
    price = request.form.get('price', '').strip()
    product.price = float(price) if price else None
    product.active = request.form.get('active') == 'on'
    db.session.commit()
    flash('Product updated.', 'success')
    return redirect(url_for('admin.dashboard') + '#products')


@admin.post('/inquiry/<int:id>/status')
@login_required
def inquiry_status(id):
    inquiry_obj = Inquiry.query.get_or_404(id)
    inquiry_obj.status = request.form.get('status', 'New')
    db.session.commit()
    return redirect(url_for('admin.dashboard') + '#inquiries')


@admin.post('/change-password')
@login_required
def change_password():
    if not check_password_hash(current_user.password_hash, request.form.get('old_password', '')):
        flash('Current password is incorrect.', 'error')
    elif len(request.form.get('new_password', '')) < 10:
        flash('New password must be at least 10 characters.', 'error')
    else:
        current_user.password_hash = generate_password_hash(request.form['new_password'])
        db.session.commit()
        flash('Password updated.', 'success')
    return redirect(url_for('admin.dashboard') + '#security')


@admin.get('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.home'))
@main.route("/sitemap.xml")
def sitemap():
    pages = [
        "/",
        "/products",
        "/livestock",
        "/about",
        "/contact"
    ]

    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
"""

    for page in pages:
        sitemap_xml += f"""    <url>
        <loc>https://shreedogadabhumiraj.onrender.com{page}</loc>
    </url>
"""

    sitemap_xml += "</urlset>"

    return sitemap_xml, 200, {"Content-Type": "application/xml"}

@main.route("/robots.txt")
def robots():
    robots_txt = """User-agent: *
Allow: /

Sitemap: https://shreedogadabhumiraj.onrender.com/sitemap.xml
"""
    return robots_txt, 200, {"Content-Type": "text/plain"}

# Individual animal management: private routes, with animal-specific vaccination records.
ANIMAL_TYPES = {'Cow', 'Buffalo', 'Calf'}
ANIMAL_STATUSES = {'Available', 'Reserved', 'Sold', 'Not Available'}
IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}


def save_animal_photo(file, previous=None):
    if not file or not file.filename:
        return previous
    suffix = Path(secure_filename(file.filename)).suffix.lower().lstrip('.')
    if suffix not in IMAGE_EXTENSIONS:
        raise ValueError('Please upload a JPG, PNG or WebP image.')
    # Check the actual file signature, not just its extension.
    signature = file.stream.read(16)
    file.stream.seek(0)
    if not (signature.startswith(b'\xff\xd8\xff') if suffix in {'jpg','jpeg'} else
            signature.startswith(b'\x89PNG\r\n\x1a\n') if suffix == 'png' else
            signature.startswith(b'RIFF') and signature[8:12] == b'WEBP'):
        raise ValueError('The selected file is not a valid image of that type.')
    file.stream.seek(0, 2)
    length = file.stream.tell()
    file.stream.seek(0)
    if length > 5 * 1024 * 1024:
        raise ValueError('Animal photos must be 5 MB or smaller.')
    folder = Path(current_app.instance_path) / 'animal_uploads'
    folder.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(16) + '.' + suffix
    file.save(folder / name)
    return name


@main.get('/animal-photo/<path:filename>')
def animal_photo(filename):
    from flask import send_from_directory
    if not Animal.query.filter_by(photo=filename, status='Available').first():
        abort(404)
    return send_from_directory(Path(current_app.instance_path) / 'animal_uploads', filename)


@admin.get('/animal-photo/<path:filename>')
@login_required
def private_animal_photo(filename):
    from flask import send_from_directory
    if not Animal.query.filter_by(photo=filename).first():
        abort(404)
    return send_from_directory(Path(current_app.instance_path) / 'animal_uploads', filename)


def fill_animal(animal):
    kind = request.form.get('animal_type', '')
    status = request.form.get('status', 'Available')
    animal_id = request.form.get('animal_id', '').strip().upper()
    breed = request.form.get('breed', '').strip()
    gender = request.form.get('gender', '')
    if kind not in ANIMAL_TYPES or status not in ANIMAL_STATUSES or gender not in {'Male', 'Female'} or not animal_id or not breed:
        raise ValueError('Enter a valid animal ID, type, breed, gender and status.')
    if Animal.query.filter(Animal.animal_id == animal_id, Animal.id != (animal.id or -1)).first():
        raise ValueError('That animal ID already exists.')
    age = float(request.form.get('age_years', '0'))
    milk = request.form.get('milk_liters', '').strip()
    price = request.form.get('price', '').strip()
    milk = float(milk) if milk else None
    price = float(price) if price else None
    if age < 0 or age > 80 or milk is not None and (milk < 0 or milk > 150) or price is not None and (price < 0 or price > 100000000):
        raise ValueError('Enter valid age, milk production and price values.')
    photo = save_animal_photo(request.files.get('photo'), animal.photo)
    animal.animal_id, animal.animal_type, animal.breed, animal.gender = animal_id, kind, breed, gender
    animal.age_years, animal.milk_liters, animal.price, animal.photo = age, milk, price, photo
    animal.color = request.form.get('color', '').strip()[:80]
    animal.health_status = request.form.get('health_status', '').strip()[:120]
    animal.description = request.form.get('description', '').strip()[:3000]
    animal.status = status


@admin.route('/animals', methods=['GET', 'POST'])
@login_required
def animals():
    if request.method == 'POST':
        animal = Animal()
        try:
            fill_animal(animal)
            db.session.add(animal)
            db.session.commit()
            flash('Animal added.', 'success')
            return redirect(url_for('admin.animals'))
        except (ValueError, TypeError, OverflowError) as exc:
            db.session.rollback()
            flash(str(exc), 'error')
    q = request.args.get('q', '').strip()
    kind = request.args.get('type', '')
    query = Animal.query
    if q:
        query = query.filter(or_(Animal.animal_id.ilike(f'%{q}%'), Animal.breed.ilike(f'%{q}%')))
    if kind in ANIMAL_TYPES:
        query = query.filter_by(animal_type=kind)
    return render_template('animals_admin.html', animals=query.order_by(Animal.id.desc()).all(), q=q, kind=kind)


@admin.route('/animal/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_animal(id):
    animal = Animal.query.get_or_404(id)
    if request.method == 'POST':
        try:
            fill_animal(animal)
            db.session.commit()
            flash('Animal updated.', 'success')
            return redirect(url_for('admin.edit_animal', id=id))
        except (ValueError, TypeError, OverflowError) as exc:
            db.session.rollback()
            flash(str(exc), 'error')
    return render_template('animal_edit.html', animal=animal, today=date.today(), upcoming_date=date.today() + timedelta(days=30))


@admin.post('/animal/<int:id>/delete')
@login_required
def delete_animal(id):
    animal = Animal.query.get_or_404(id)
    db.session.delete(animal)
    db.session.commit()
    flash('Animal and its vaccination history deleted.', 'success')
    return redirect(url_for('admin.animals'))


def vaccination_fields(v):
    name = request.form.get('vaccine_name', '').strip()
    if not name:
        raise ValueError('Vaccine name is required.')
    given = date.fromisoformat(request.form['date_given'])
    due = date.fromisoformat(request.form['next_due']) if request.form.get('next_due') else None
    if due and due < given:
        raise ValueError('Next due date cannot be earlier than the vaccination date.')
    v.vaccine_name, v.date_given, v.next_due = name[:150], given, due
    v.purpose = request.form.get('purpose', '').strip()[:150]
    v.notes = request.form.get('notes', '').strip()[:3000]


@admin.post('/animal/<int:id>/vaccination')
@login_required
def add_vaccination(id):
    animal = Animal.query.get_or_404(id)
    v = Vaccination(animal=animal)
    try:
        vaccination_fields(v)
        db.session.add(v)
        db.session.commit()
        flash('Vaccination recorded.', 'success')
    except (ValueError, KeyError) as exc:
        db.session.rollback()
        flash('Invalid vaccination: ' + str(exc), 'error')
    return redirect(url_for('admin.edit_animal', id=id) + '#vaccinations')


@admin.post('/animal/<int:id>/vaccination/<int:vid>/edit')
@login_required
def edit_vaccination(id, vid):
    v = Vaccination.query.filter_by(id=vid, animal_id=id).first_or_404()
    try:
        vaccination_fields(v)
        db.session.commit()
        flash('Vaccination updated.', 'success')
    except (ValueError, KeyError) as exc:
        db.session.rollback()
        flash('Invalid vaccination: ' + str(exc), 'error')
    return redirect(url_for('admin.edit_animal', id=id) + '#vaccinations')


@admin.post('/animal/<int:id>/vaccination/<int:vid>/delete')
@login_required
def delete_vaccination(id, vid):
    v = Vaccination.query.filter_by(id=vid, animal_id=id).first_or_404()
    db.session.delete(v)
    db.session.commit()
    flash('Vaccination removed.', 'success')
    return redirect(url_for('admin.edit_animal', id=id) + '#vaccinations')
