from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from pathlib import Path
db=SQLAlchemy(); login_manager=LoginManager(); login_manager.login_view="admin.login"
def create_app():
    app=Flask(__name__); app.config.from_object("config.Config")
    Path(app.instance_path).mkdir(parents=True,exist_ok=True)
    db.init_app(app); login_manager.init_app(app)
    app.jinja_env.filters["fromjson"]=lambda v: __import__("json").loads(v)
    from .routes import main,admin
    app.register_blueprint(main); app.register_blueprint(admin,url_prefix="/owner")
    with app.app_context():
        from .models import Product,Admin,Animal,Vaccination
        db.create_all(); seed()
    return app
def seed():
    from .models import Product,Admin
    from werkzeug.security import generate_password_hash
    import os
    if not Product.query.first():
        data=[
        ("Cow Milk","cow-milk",80,"liter","Dairy","Fresh local cow milk.","🥛"),
        ("Buffalo Milk","buffalo-milk",90,"liter","Dairy","Rich and creamy buffalo milk.","🥛"),
        ("Dahi","dahi",120,"kg","Dairy","Fresh traditional yogurt.","🥣"),
        ("Mahi","mahi",70,"liter","Dairy","Refreshing traditional dairy drink.","🫗"),
        ("Paneer","paneer",700,"kg","Dairy","Fresh paneer made from quality milk.","🧀"),
        ("Ghee","ghee",1000,"kg","Dairy","Rich dairy ghee.","🫙"),
        ("Cow","cow",None,"on request","Livestock","Healthy cows. Ask about breed, age, availability and price.","🐄"),
        ("Buffalo","buffalo",None,"on request","Livestock","Buffalo available based on current stock.","🐃"),
        ("Calf","calf",None,"on request","Livestock","Calves available based on current stock.","🐮")]
        db.session.add_all([Product(name=a,slug=b,price=c,unit=d,category=e,description=f,icon=g) for a,b,c,d,e,f,g in data]); db.session.commit()
       owner = Admin.query.filter_by(username="owner").first()

    # Create owner account on first deployment
    if not owner:
        password = os.environ.get("INITIAL_OWNER_PASSWORD")
        if password and len(password) >= 10:
            db.session.add(
                Admin(
                    username="owner",
                    password_hash=generate_password_hash(password)
                )
            )
            db.session.commit()
        else:
            app_logger = __import__('logging').getLogger(__name__)
            app_logger.warning(
                'No owner account created. Set INITIAL_OWNER_PASSWORD '
                '(at least 10 characters) before first deployment.'
            )

    # Temporary password reset for an existing owner
    reset_password = os.environ.get("RESET_OWNER_PASSWORD")

    if reset_password and len(reset_password) >= 10:
        owner = Admin.query.filter_by(username="owner").first()

        if owner:
            owner.password_hash = generate_password_hash(reset_password)
            db.session.commit()
            app_logger = __import__('logging').getLogger(__name__)
            app_logger.warning("Owner password has been reset using RESET_OWNER_PASSWORD.")