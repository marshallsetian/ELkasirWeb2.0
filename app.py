from flask import Flask ,session
from flask_login import LoginManager
from models import db, MainUser
from routes import init_routes
from config import Config
from flask_migrate import Migrate


app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "elproject"

# Init DB
db.init_app(app)
with app.app_context():
    db.create_all()

# Init Flask-Login
login_manager = LoginManager()
login_manager.login_view = "login"  # redirect ke /login kalau belum login
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return MainUser.query.get(int(user_id))

# Custom filter Rupiah
def rupiah(value):
    try:
        return f"Rp {int(value):,}".replace(",", ".")
    except Exception:
        return "Rp 0"

app.jinja_env.filters["rupiah"] = rupiah


# setelah db didefinisikan
migrate = Migrate(app, db)


# Register all routes
init_routes(app)

if __name__ == "__main__":
    app.run(debug=True)
