from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
import os
from . import db
from .models import Product, Order, Inquiry, Admin, Animal, Vaccination, LoginAttempt
import json
import math
import requests
from datetime import date, datetime, timedelta
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app, abort, session
from sqlalchemy import or_
import secrets
import time
import hmac
import hashlib

main = Blueprint('main', __name__)
admin = Blueprint('admin', __name__)

# Database-backed login throttle: persists across app workers/restarts.
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_LOCK_SECONDS = 15 * 60
_LOGIN_MAX_ATTEMPTS = 5

def login_ip_digest(ip_address):
    key = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(key, (ip_address or "unknown").encode("utf-8"), hashlib.sha256).hexdigest()

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

@main.get('/product-image/<slug>')
def product_image(slug):
    from flask import send_from_directory

    product = Product.query.filter_by(slug=slug, active=True).first_or_404()

    folder = Path(current_app.instance_path) / 'product_uploads'
    uploaded_image = folder / f'product_{product.id}.jpg'

    if uploaded_image.is_file():
        return send_from_directory(folder, uploaded_image.name, max_age=0)

    fallback_images = {
        'cow-milk': 'cowmilk.jpeg',
        'buffalo-milk': 'buffalomilk.jpeg',
        'dahi': 'dhai.jpeg',
        'mahi': 'mahi.jpeg',
        'paneer': 'paneer.jpeg',
        'ghee': 'ghee.jpg'
    }

    fallback = fallback_images.get(product.slug)

    if fallback:
        return send_from_directory(
            current_app.static_folder + '/images',
            fallback,
            max_age=0
        )

    abort(404)
@main.get('/livestock')
def livestock():
    return render_template('livestock.html', animals=Animal.query.filter_by(status='Available').order_by(Animal.animal_type, Animal.id.desc()).all())


@main.get('/about')
def about():
    return render_template('about.html')


@main.get('/contact')
def contact():
    return render_template('contact.html')


@main.get('/privacy')
def privacy_policy():
    return render_template('privacy.html')


@main.get('/terms')
def terms_of_service():
    return render_template('terms.html')


@main.get('/subprocessors')
def subprocessors():
    return render_template('subprocessors.html')


@main.get('/dpa')
def dpa():
    return render_template('dpa.html')


@main.route('/data-rights', methods=['GET', 'POST'])
def data_rights():
    if request.method == 'GET':
        return render_template('data_rights.html')
    order_code = request.form.get('order_code', '').strip().upper()
    phone = request.form.get('phone', '').strip()
    action = request.form.get('action', 'export')
    order = Order.query.filter_by(order_code=order_code, phone=phone).first()
    if not order:
        flash('We could not verify that order using those details. Check the order code and phone number.', 'error')
        return redirect(url_for('main.data_rights'))
    if action == 'delete':
        # Preserve a minimal transaction record where needed for accounting/disputes,
        # while removing direct customer identifiers and free-text personal details.
        order.customer_name = '[deleted]'
        order.phone = '[deleted]'
        order.email = None
        order.address = '[deleted]'
        order.notes = None
        db.session.commit()
        flash('Personal details for this order have been erased from the active order record. Limited transaction data may be retained where legally necessary.', 'success')
        return redirect(url_for('main.data_rights'))
    if action != 'export':
        flash('Choose a valid data request.', 'error')
        return redirect(url_for('main.data_rights'))
    payload = {
        'order_code': order.order_code, 'customer_name': order.customer_name,
        'phone': order.phone, 'email': order.email, 'address': order.address,
        'items': json.loads(order.items_json), 'subtotal': order.subtotal,
        'delivery_charge': order.delivery_charge, 'total': order.total,
        'notes': order.notes, 'status': order.status,
        'payment_method': order.payment_method,
        'created_at': order.created_at.isoformat() if order.created_at else None
    }
    from flask import Response
    return Response(json.dumps(payload, ensure_ascii=False, indent=2), mimetype='application/json',
                    headers={'Content-Disposition': f'attachment; filename="{order.order_code}-data-export.json"',
                             'Cache-Control': 'no-store'})


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
    accepted_terms = request.form.get('accept_terms') == 'yes'
    payment = request.form.get('payment_method', 'Cash on Delivery')
    allowed_payments = {'Cash on Delivery', 'Bank Transfer'}
    if payment not in allowed_payments:
        flash('Please select a valid payment method.', 'error')
        return redirect(url_for('main.checkout'))
    if not accepted_terms:
        flash('Please accept the Terms of Service and Privacy Policy to place an order.', 'error')
        return redirect(url_for('main.checkout'))
    if not name or not phone or not address or not cart:
        flash('Please complete your details and add products.', 'error')
        return redirect(url_for('main.checkout'))
    if len(name) > 120 or len(phone) > 40 or len(email) > 160 or len(address) > 1500 or len(notes) > 1000:
        flash('One or more fields are too long. Please review your details.', 'error')
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

    code = 'SD-' + secrets.token_hex(13).upper()
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
    # The high-entropy order code is an unguessable receipt reference.
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
    if len(name) > 120 or len(phone) > 40 or len(email) > 160 or len(msg) > 3000:
        flash('One or more fields are too long. Please review your message.', 'error')
        return redirect(url_for('main.contact'))
    db.session.add(Inquiry(name=name, phone=phone, email=email, message=msg))
    db.session.commit()
    flash('Your message has been sent.', 'success')
    return redirect(url_for('main.contact'))


@admin.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    digest = login_ip_digest(request.remote_addr)
    now = datetime.utcnow()
    attempt = db.session.get(LoginAttempt, digest)

    if attempt and attempt.locked_until and attempt.locked_until > now:
        remaining = max(1, int((attempt.locked_until - now).total_seconds() / 60) + 1)
        flash(f'Too many failed attempts. Try again in about {remaining} minute(s).', 'error')
        return render_template('owner_login.html'), 429

    if request.method == 'POST':
        username = request.form.get('username', '').strip()[:80]
        password = request.form.get('password', '')
        user = Admin.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            if attempt:
                db.session.delete(attempt)
                db.session.commit()
            session.clear()
            login_user(user, remember=False, fresh=True)
            return redirect(url_for('admin.dashboard'))

        # Only persist a throttle row after an unsuccessful authentication.
        if not attempt:
            attempt = LoginAttempt(ip_digest=digest, failures=0, window_started=now)
            db.session.add(attempt)
        elif (now - attempt.window_started).total_seconds() >= _LOGIN_WINDOW_SECONDS:
            attempt.failures = 0
            attempt.window_started = now
            attempt.locked_until = None

        attempt.failures += 1
        if attempt.failures >= _LOGIN_MAX_ATTEMPTS:
            attempt.locked_until = now + timedelta(seconds=_LOGIN_LOCK_SECONDS)
        db.session.commit()
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

    return render_template(
        'orders_admin.html',
        orders=query.order_by(Order.created_at.desc()).all(),
        selected=selected,
        statuses=statuses,
        counts={
            status: sum(
                1 for order in all_orders
                if status == 'All' or order.status == status
            )
            for status in statuses
        }
    )


@admin.post('/order/<int:id>/status')
@login_required
def order_status(id):
    order = Order.query.get_or_404(id)
    status = request.form.get('status')

    allowed = [
        'New', 'Confirmed', 'Preparing',
        'Out for Delivery', 'Delivered', 'Cancelled'
    ]

    if status in allowed:
        order.status = status
        db.session.commit()

    return redirect(
        url_for('admin.orders', status=request.form.get('filter_status', 'All'))
    )


@admin.post('/product/<int:id>/save')
@login_required
def product_save(id):
    product = Product.query.get_or_404(id)

    product.name = request.form.get('name', product.name)
    product.unit = request.form.get('unit', product.unit)
    product.description = request.form.get('description', product.description)

    price = request.form.get('price', '').strip()

    try:
        parsed_price = float(price) if price else None

        if parsed_price is not None and (
            not math.isfinite(parsed_price)
            or parsed_price < 0
            or parsed_price > 100000000
        ):
            raise ValueError

    except (ValueError, TypeError, OverflowError):
        flash('Enter a valid non-negative price up to Rs. 100,000,000.', 'error')
        return redirect(url_for('admin.dashboard') + '#products')

    product.price = parsed_price
    product.active = request.form.get('active') == 'on'

    db.session.commit()

    flash('Product updated.', 'success')
    return redirect(url_for('admin.dashboard') + '#products')


# Secure product image upload
@admin.post('/product/<int:id>/image')
@login_required
def product_image_upload(id):

    product = Product.query.get_or_404(id)
    uploaded = request.files.get('image')

    if not uploaded or not uploaded.filename:
        return jsonify(
            success=False,
            error='Please select an image.'
        ), 400

    try:
        raw = uploaded.read(5 * 1024 * 1024 + 1)

        if not raw or len(raw) > 5 * 1024 * 1024:
            raise ValueError('Image must be 5 MB or smaller.')

        try:
            with Image.open(BytesIO(raw)) as check:

                if check.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValueError(
                        'Only JPG, PNG and WebP images are allowed.'
                    )

                if check.width < 100 or check.height < 100:
                    raise ValueError(
                        'Image dimensions must be at least 100 × 100 pixels.'
                    )

                if check.width > 12000 or check.height > 12000:
                    raise ValueError('Image dimensions are too large.')

                if check.width * check.height > 40000000:
                    raise ValueError('Image resolution is too large.')

                check.verify()

            with Image.open(BytesIO(raw)) as original:

                image = ImageOps.exif_transpose(original)
                image = image.convert('RGB')

                output = BytesIO()

                image.save(
                    output,
                    format='JPEG',
                    quality=88,
                    optimize=True
                )

                output.seek(0)

        except (UnidentifiedImageError, OSError):
            raise ValueError('The selected file is not a valid image.')

        folder = Path(current_app.instance_path) / 'product_uploads'
        folder.mkdir(parents=True, exist_ok=True)

        destination = folder / f'product_{product.id}.jpg'

        temporary = folder / (
            f'product_{product.id}_{secrets.token_hex(8)}.tmp'
        )

        temporary.write_bytes(output.getvalue())
        os.replace(temporary, destination)

        return jsonify(
            success=True,
            message='Product image saved successfully.'
        )

    except ValueError as error:
        return jsonify(
            success=False,
            error=str(error)
        ), 400

    except Exception:
        current_app.logger.exception('Product image upload failed.')

        return jsonify(
            success=False,
            error='Unable to save the image. Please try again.'
        ), 500
@login_required
def inquiry_status(id):
    inquiry_obj = Inquiry.query.get_or_404(id)
    status = request.form.get('status', 'New')
    if status not in {'New', 'Contacted', 'Closed'}:
        flash('Invalid inquiry status.', 'error')
        return redirect(url_for('admin.dashboard') + '#inquiries')
    inquiry_obj.status = status
    db.session.commit()
    return redirect(url_for('admin.dashboard') + '#inquiries')


@admin.post('/change-password')
@login_required
def change_password():
    if not check_password_hash(current_user.password_hash, request.form.get('old_password', '')):
        flash('Current password is incorrect.', 'error')
    elif len(request.form.get('new_password', '')) < 12:
        flash('New password must be at least 12 characters.', 'error')
    else:
        current_user.password_hash = generate_password_hash(request.form['new_password'])
        db.session.commit()
        flash('Password updated.', 'success')
    return redirect(url_for('admin.dashboard') + '#security')


@admin.post('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('main.home'))
@main.get("/sitemap.xml")
def sitemap():
    site_url = current_app.config.get("SITE_URL", "https://shreedogadabhumiraj.onrender.com").rstrip("/")
    pages = ["/", "/products", "/livestock", "/about", "/contact", "/privacy", "/terms", "/subprocessors", "/dpa", "/data-rights"]
    sitemap_xml = ['<?xml version="1.0" encoding="UTF-8"?>',
                   '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in pages:
        sitemap_xml.append(f"  <url><loc>{site_url}{page}</loc></url>")
    sitemap_xml.append("</urlset>")
    from flask import Response
    return Response("\\n".join(sitemap_xml), status=200, mimetype="application/xml")


@main.get("/robots.txt")
def robots():
    site_url = current_app.config.get("SITE_URL", "https://shreedogadabhumiraj.onrender.com").rstrip("/")
    return f"User-agent: *\\nAllow: /\\n\\nSitemap: {site_url}/sitemap.xml\\n", 200, {"Content-Type": "text/plain; charset=utf-8"}


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
    if len(animal_id) > 40 or len(breed) > 100:
        raise ValueError('Animal ID must be at most 40 characters and breed at most 100 characters.')
    age = float(request.form.get('age_years', '0'))
    milk = request.form.get('milk_liters', '').strip()
    price = request.form.get('price', '').strip()
    milk = float(milk) if milk else None
    price = float(price) if price else None
    if (not math.isfinite(age) or age < 0 or age > 80
            or milk is not None and (not math.isfinite(milk) or milk < 0 or milk > 150)
            or price is not None and (not math.isfinite(price) or price < 0 or price > 100000000)):
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
