from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, make_response
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from sqlalchemy import func, or_
from . import db
from .models import Product
from .dairy_models import *
import secrets, csv, io, hmac, hashlib
from flask import current_app

dairy=Blueprint('dairy',__name__,url_prefix='/dairy')

def audit(action, details=''):
    db.session.add(DairyAudit(actor=getattr(current_user,'username','owner'), action=action, details=details[:4000]))

def customer_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapped(*a,**kw):
        cid=session.get('dairy_customer_id')
        c=db.session.get(DairyCustomer,cid) if cid else None
        if not c or c.status in ('closed','archived'):
            session.pop('dairy_customer_id',None); return redirect(url_for('dairy.customer_login'))
        return fn(c,*a,**kw)
    return wrapped

def money(v):
    try: return Decimal(str(v)).quantize(Decimal('0.01'))
    except (InvalidOperation,TypeError): raise ValueError('Enter a valid amount.')
def quantity(v):
    q=Decimal(str(v))
    if q<0 or q>10000: raise ValueError('Quantity must be between 0 and 10000.')
    return q.quantize(Decimal('0.001'))
def balance(cid):
    row=db.session.query(func.coalesce(func.sum(DairyLedger.debit),0)-func.coalesce(func.sum(DairyLedger.credit),0)).filter_by(customer_id=cid).scalar()
    return Decimal(str(row or 0)).quantize(Decimal('0.01'))
def add_charge(cid, day, amount, desc, source, sid):
    if DairyLedger.query.filter_by(source_type=source,source_id=sid,kind='charge').first(): return
    db.session.add(DairyLedger(customer_id=cid,entry_date=day,kind='charge',debit=money(amount),credit=0,description=desc,source_type=source,source_id=sid))

def active_subs(c,day):
    return DairySubscription.query.filter(DairySubscription.customer_id==c.id,DairySubscription.effective_from<=day,or_(DairySubscription.effective_until==None,DairySubscription.effective_until>=day)).all()

@dairy.get('/owner')
@login_required
def owner_home():
    customers=DairyCustomer.query.order_by(DairyCustomer.name).all()
    today=date.today()
    return render_template('dairy_owner.html',customers=customers,products=Product.query.filter_by(active=True).all(),today=today,total_due=sum((balance(c.id) for c in customers),Decimal('0')),balances={c.id:balance(c.id) for c in customers})

@dairy.route('/owner/customer/new',methods=['POST'])
@login_required
def create_customer():
    try:
        name=request.form['name'].strip(); username=request.form['username'].strip().lower(); password=request.form['password']; start=date.fromisoformat(request.form.get('start_date') or date.today().isoformat())
        if not name or len(password)<10: raise ValueError('Name is required and password must be at least 10 characters.')
        if DairyCustomer.query.filter_by(username=username).first(): raise ValueError('That username already exists.')
        code='SD-'+secrets.token_hex(3).upper()
        c=DairyCustomer(code=code,name=name,username=username,password_hash=generate_password_hash(password),phone=request.form.get('phone','').strip(),address=request.form.get('address','').strip(),start_date=start)
        db.session.add(c); db.session.flush()
        product_ids=request.form.getlist('product_id'); quantities=request.form.getlist('regular_quantity')
        for pid,q in zip(product_ids,quantities):
            if q.strip() and Decimal(q)>0:
                p=Product.query.get(int(pid))
                if p and p.active and p.unit.lower() in ('liter','litre','l','kg','kilogram'):
                    db.session.add(DairySubscription(customer_id=c.id,product_id=p.id,quantity=quantity(q),effective_from=start))
        audit('customer_created',f'{code} {name} ({username})'); db.session.commit(); flash(f'Customer created. ID: {code}','success')
    except ValueError as e: db.session.rollback(); flash(str(e),'error')
    except Exception:
        db.session.rollback(); current_app.logger.exception('Dairy operation failed'); flash('Unable to complete that operation. Please check the information and try again.','error')
    return redirect(url_for('dairy.owner_home'))

@dairy.post('/owner/product/new')
@login_required
def create_dairy_product():
    try:
        name=request.form.get('name','').strip(); unit=request.form.get('unit','')
        price=money(request.form.get('price',''))
        if not name or unit not in ('liter','kg') or price<0: raise ValueError('Enter a product name, unit L/kg and valid non-negative price.')
        import re
        slug=re.sub(r'[^a-z0-9]+','-',name.lower()).strip('-')[:110]
        if not slug: raise ValueError('Product name is not valid.')
        if Product.query.filter_by(slug=slug).first(): slug=f"{slug}-{secrets.token_hex(2)}"
        p=Product(name=name,slug=slug,price=float(price),unit=unit,category='Dairy',description=request.form.get('description','').strip() or f'Fresh {name}.',icon='🥛',active=True)
        db.session.add(p); audit('dairy_product_created',f'{name} {price}/{unit}'); db.session.commit(); flash('Product added to the farm catalogue.','success')
    except ValueError as e: db.session.rollback(); flash(str(e),'error')
    except Exception:
        db.session.rollback(); current_app.logger.exception('Dairy operation failed'); flash('Unable to complete that operation. Please check the information and try again.','error')
    return redirect(url_for('dairy.owner_home'))

@dairy.post('/owner/customer/<int:cid>/subscription')
@login_required
def subscription(cid):
    c=DairyCustomer.query.get_or_404(cid)
    try:
        day=date.fromisoformat(request.form['effective_from']); p=Product.query.get_or_404(int(request.form['product_id'])); q=quantity(request.form['quantity'])
        if p.unit.lower() not in ('liter','litre','l','kg','kilogram') or q<=0: raise ValueError('Choose a dairy product and positive quantity.')
        old=DairySubscription.query.filter_by(customer_id=cid,product_id=p.id,effective_until=None).first()
        if old:
            if day<=old.effective_from: raise ValueError('Effective date must be after the existing start date.')
            old.effective_until=day-timedelta(days=1)
        db.session.add(DairySubscription(customer_id=cid,product_id=p.id,quantity=q,effective_from=day)); audit('subscription_changed',f'{c.code} {p.name} {q} from {day}'); db.session.commit(); flash('Regular quantity updated. Earlier delivery history is unchanged.','success')
    except ValueError as e: db.session.rollback(); flash(str(e),'error')
    except Exception:
        db.session.rollback(); current_app.logger.exception('Dairy operation failed'); flash('Unable to complete that operation. Please check the information and try again.','error')
    return redirect(url_for('dairy.owner_home'))

@dairy.post('/owner/customer/<int:cid>/status')
@login_required
def customer_status(cid):
    c=DairyCustomer.query.get_or_404(cid); action=request.form.get('status')
    if action=='paused': c.status='paused'; c.pause_until=date.fromisoformat(request.form['pause_until']) if request.form.get('pause_until') else None
    elif action=='active': c.status='active'; c.pause_until=None
    elif action=='closed': c.status='closed'
    audit('customer_status',f'{c.code}: {c.status}'); db.session.commit(); flash('Customer status updated.','success'); return redirect(url_for('dairy.owner_home'))

@dairy.route('/owner/deliveries',methods=['GET','POST'])
@login_required
def deliveries():
    day=date.fromisoformat(request.values.get('day') or date.today().isoformat())
    for paused in DairyCustomer.query.filter_by(status='paused').all():
        if paused.pause_until and paused.pause_until < day: paused.status='active'; paused.pause_until=None
    db.session.commit()
    customers=DairyCustomer.query.filter_by(status='active').order_by(DairyCustomer.name).all()
    if request.method=='POST':
        try:
            cid=int(request.form['customer_id']); pid=int(request.form['product_id']); c=DairyCustomer.query.get_or_404(cid); p=Product.query.get_or_404(pid)
            if c.status!='active': raise ValueError('Paused or closed customers cannot receive regular deliveries.')
            expected=quantity(request.form.get('expected',0)); delivered=quantity(request.form.get('delivered',0)); status=request.form.get('status','delivered')
            if status not in ('delivered','no_delivery'): raise ValueError('Invalid delivery status.')
            if status=='no_delivery': delivered=Decimal('0')
            rec=DairyDelivery.query.filter_by(customer_id=cid,product_id=pid,delivery_date=day).first()
            old=f'{rec.delivered_quantity}/{rec.status}' if rec else 'not recorded'
            if not rec: rec=DairyDelivery(customer_id=cid,product_id=pid,delivery_date=day,expected_quantity=expected,delivered_quantity=delivered,unit_price=money(p.price or 0),status=status,recorded_by='owner'); db.session.add(rec)
            else: rec.expected_quantity=expected; rec.delivered_quantity=delivered; rec.status=status; rec.notes=request.form.get('notes',''); rec.recorded_by='owner'
            db.session.flush()
            # Rebuild this source charge safely if an owner edits a previously posted record.
            prior=DairyLedger.query.filter_by(source_type='delivery',source_id=rec.id,kind='charge').first()
            if prior:
                if delivered>0: prior.debit=money(delivered*rec.unit_price); prior.description=f'{p.name} {delivered} {p.unit} delivered on {day}'
                else: db.session.delete(prior)
            elif delivered>0: add_charge(cid,day,delivered*rec.unit_price,f'{p.name} {delivered} {p.unit} delivered on {day}','delivery',rec.id)
            audit('delivery_saved',f'{c.code} {p.name} {day}: {old} -> {delivered}/{status}; reason={request.form.get("notes","")}'); db.session.commit(); flash('Delivery saved.','success')
        except ValueError as e: db.session.rollback(); flash(str(e),'error')
        except Exception:
            db.session.rollback(); current_app.logger.exception('Dairy operation failed'); flash('Unable to complete that operation. Please check the information and try again.','error')
        return redirect(url_for('dairy.deliveries',day=day.isoformat()))
    rows=[]
    for c in customers:
        if c.status=='paused' and (not c.pause_until or c.pause_until>=day): continue
        for s in active_subs(c,day):
            rec=DairyDelivery.query.filter_by(customer_id=c.id,product_id=s.product_id,delivery_date=day).first()
            rows.append({'customer':c,'subscription':s,'record':rec})
    return render_template('dairy_deliveries.html',day=day,rows=rows)

@dairy.route('/owner/extra',methods=['GET','POST'])
@login_required
def extra_order():
    if request.method=='POST':
        try:
            c=DairyCustomer.query.get_or_404(int(request.form['customer_id'])); day=date.fromisoformat(request.form.get('order_date') or date.today().isoformat()); p=Product.query.get_or_404(int(request.form['product_id'])); q=quantity(request.form['quantity'])
            if q<=0 or p.unit.lower() not in ('liter','litre','l','kg','kilogram'): raise ValueError('Choose a dairy product with L or kg units and a positive quantity.')
            order=DairyExtraOrder(customer_id=c.id,order_date=day,notes=request.form.get('notes','')); db.session.add(order); db.session.flush(); item=DairyExtraItem(order_id=order.id,product_id=p.id,quantity=q,unit_price=money(p.price or 0)); db.session.add(item); db.session.flush(); add_charge(c.id,day,q*item.unit_price,f'Extra order #{order.id}: {p.name} {q} {p.unit}','extra_order',order.id); audit('extra_order',f'{c.code} order #{order.id}'); db.session.commit(); flash(f'Extra order #{order.id} saved.','success')
        except ValueError as e: db.session.rollback(); flash(str(e),'error')
        except Exception:
            db.session.rollback(); current_app.logger.exception('Dairy operation failed'); flash('Unable to complete that operation. Please check the information and try again.','error')
        return redirect(url_for('dairy.extra_order'))
    return render_template('dairy_extra.html',now=date.today().isoformat(),customers=DairyCustomer.query.filter(DairyCustomer.status!='archived').order_by(DairyCustomer.name).all(),products=Product.query.filter_by(active=True).all(),orders=DairyExtraOrder.query.order_by(DairyExtraOrder.id.desc()).limit(100).all())

@dairy.route('/owner/payments',methods=['GET','POST'])
@login_required
def payments():
    if request.method=='POST':
        try:
            c=DairyCustomer.query.get_or_404(int(request.form['customer_id'])); amount=money(request.form['amount']); day=date.fromisoformat(request.form.get('payment_date') or date.today().isoformat()); method=request.form['method']
            if amount<=0 or method not in ('Cash','eSewa','Khalti','Bank transfer'): raise ValueError('Enter a positive amount and valid method.')
            ledger=DairyLedger(customer_id=c.id,entry_date=day,kind='payment',debit=0,credit=amount,description=f'Payment received via {method}') ; db.session.add(ledger); db.session.flush(); pay=DairyPayment(customer_id=c.id,payment_date=day,amount=amount,method=method,reference=request.form.get('reference',''),note=request.form.get('note',''),ledger_id=ledger.id); db.session.add(pay); db.session.flush()
            remaining=amount
            selected_charge=request.form.get('charge_id','').strip()
            if selected_charge:
                ch=DairyLedger.query.filter_by(id=int(selected_charge),customer_id=c.id,kind='charge').first()
                if not ch: raise ValueError('Selected charge does not belong to this customer.')
                allocated=sum((Decimal(str(a.amount)) for a in DairyAllocation.query.filter_by(charge_ledger_id=ch.id).all()),Decimal('0'))
                due=Decimal(str(ch.debit))-allocated
                if due<=0: raise ValueError('That charge is already fully allocated.')
                part=min(due,remaining); db.session.add(DairyAllocation(payment_id=pay.id,charge_ledger_id=ch.id,amount=part)); remaining-=part
            audit('payment_received',f'{c.code} Rs {amount} via {method}; allocated to selected charge; unallocated customer credit Rs {remaining}'); db.session.commit(); flash(f'Payment recorded. Current balance: Rs {balance(c.id)}','success')
        except ValueError as e: db.session.rollback(); flash(str(e),'error')
        except Exception:
            db.session.rollback(); current_app.logger.exception('Dairy operation failed'); flash('Unable to complete that operation. Please check the information and try again.','error')
        return redirect(url_for('dairy.payments'))
    return render_template('dairy_payments.html',today=date.today().isoformat(),customers=DairyCustomer.query.order_by(DairyCustomer.name).all(),payments=DairyPayment.query.order_by(DairyPayment.id.desc()).limit(100).all(),balances={c.id:balance(c.id) for c in DairyCustomer.query.all()},charges=DairyLedger.query.filter_by(kind='charge').order_by(DairyLedger.entry_date.desc()).limit(200).all())

@dairy.post('/owner/invoice/<int:cid>')
@login_required
def make_invoice(cid):
    c=DairyCustomer.query.get_or_404(cid)
    try:
        start=date.fromisoformat(request.form['start_date']); end=date.fromisoformat(request.form['end_date'])
        if end<start: raise ValueError('End date must be after start date.')
        existing=DairyInvoice.query.filter_by(customer_id=cid,start_date=start,end_date=end).first()
        if existing: raise ValueError('An invoice already exists for this period.')
        charges=DairyLedger.query.filter(DairyLedger.customer_id==cid,DairyLedger.kind=='charge',DairyLedger.entry_date>=start,DairyLedger.entry_date<=end).all(); total=sum((Decimal(str(x.debit)) for x in charges),Decimal('0'))
        inv=DairyInvoice(customer_id=cid,start_date=start,end_date=end,total=total); db.session.add(inv); audit('invoice_created',f'{c.code} {start} to {end} total {total}'); db.session.commit(); flash(f'Statement created: Rs {total}. Charges remain in ledger and are not duplicated.','success')
    except ValueError as e: db.session.rollback(); flash(str(e),'error')
    except Exception:
        db.session.rollback(); current_app.logger.exception('Dairy operation failed'); flash('Unable to complete that operation. Please check the information and try again.','error')
    return redirect(url_for('dairy.owner_home'))

@dairy.get('/owner/statement/<int:cid>')
@login_required
def statement(cid):
    c=DairyCustomer.query.get_or_404(cid); entries=DairyLedger.query.filter_by(customer_id=cid).order_by(DairyLedger.entry_date,DairyLedger.id).all(); invoices=DairyInvoice.query.filter_by(customer_id=cid).order_by(DairyInvoice.id.desc()).all(); return render_template('dairy_statement.html',customer=c,entries=entries,invoices=invoices,balance=balance(cid))

@dairy.get('/owner/export.csv')
@login_required
def export_csv():
    out=io.StringIO(); w=csv.writer(out); w.writerow(['Customer ID','Customer','Date','Type','Debit','Credit','Description'])
    for x in DairyLedger.query.order_by(DairyLedger.entry_date).all(): w.writerow([x.customer.code,x.customer.name,x.entry_date,x.kind,x.debit,x.credit,x.description])
    resp=make_response('\ufeff'+out.getvalue()); resp.headers['Content-Type']='text/csv; charset=utf-8'; resp.headers['Content-Disposition']='attachment; filename=dairy-ledger.csv'; return resp

@dairy.route('/customer/login',methods=['GET','POST'])
def customer_login():
    # Persistent per-IP throttling works across Gunicorn workers and restarts.
    ip = request.remote_addr or 'unknown'
    digest = hmac.new(current_app.config['SECRET_KEY'].encode('utf-8'), ip.encode('utf-8'), hashlib.sha256).hexdigest()
    now = datetime.utcnow()
    attempt = db.session.get(DairyLoginAttempt, digest)
    if attempt and attempt.locked_until and attempt.locked_until > now:
        flash('Too many failed attempts. Please try again in 15 minutes.', 'error')
        return render_template('dairy_customer_login.html'), 429
    if request.method == 'POST':
        c=DairyCustomer.query.filter_by(username=request.form.get('username','').strip().lower()).first()
        if c and c.status not in ('closed','archived') and check_password_hash(c.password_hash,request.form.get('password','')):
            if attempt:
                db.session.delete(attempt)
                db.session.commit()
            session.clear()
            session['dairy_customer_id']=c.id
            session.permanent=True
            return redirect(url_for('dairy.customer_dashboard'))
        if not attempt:
            attempt=DairyLoginAttempt(ip_digest=digest, failures=0, window_started=now)
            db.session.add(attempt)
        elif (now-attempt.window_started).total_seconds() >= 900:
            attempt.failures=0
            attempt.window_started=now
            attempt.locked_until=None
        attempt.failures += 1
        if attempt.failures >= 5:
            attempt.locked_until=now+timedelta(minutes=15)
        db.session.commit()
        flash('Invalid login or account unavailable.', 'error')
    return render_template('dairy_customer_login.html')

@dairy.post('/customer/logout')
def customer_logout(): session.pop('dairy_customer_id',None); return redirect(url_for('dairy.customer_login'))

@dairy.get('/customer')
@customer_required
def customer_dashboard(c):
    entries=DairyLedger.query.filter_by(customer_id=c.id).order_by(DairyLedger.entry_date.desc()).limit(100).all(); deliveries=DairyDelivery.query.filter_by(customer_id=c.id).order_by(DairyDelivery.delivery_date.desc()).limit(60).all(); payments_list=DairyPayment.query.filter_by(customer_id=c.id).order_by(DairyPayment.payment_date.desc()).all(); requests=DairyRequest.query.filter_by(customer_id=c.id).order_by(DairyRequest.id.desc()).all()
    return render_template('dairy_customer.html',customer=c,entries=entries,deliveries=deliveries,payments=payments_list,balance=balance(c.id),requests=requests)

@dairy.post('/customer/request')
@customer_required
def customer_request(c):
    msg=request.form.get('message','').strip()
    if msg: db.session.add(DairyRequest(customer_id=c.id,message=msg)); db.session.commit(); flash('Your request has been sent to the farm.','success')
    return redirect(url_for('dairy.customer_dashboard'))

@dairy.get('/owner/requests')
@login_required
def requests_owner(): return render_template('dairy_requests.html',requests=DairyRequest.query.order_by(DairyRequest.id.desc()).all())

@dairy.post('/owner/request/<int:rid>')
@login_required
def resolve_request(rid):
    r=DairyRequest.query.get_or_404(rid); r.status=request.form.get('status','pending'); r.owner_reply=request.form.get('reply','')[:1000]; audit('customer_request_updated',f'request {rid} {r.status}'); db.session.commit(); flash('Request updated.','success'); return redirect(url_for('dairy.requests_owner'))
