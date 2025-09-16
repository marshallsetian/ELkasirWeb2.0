# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# DB utama untuk login
class MainUser(UserMixin, db.Model):
    __tablename__ = "main_user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# Tabel per user
class UserProduct(db.Model):
    __tablename__ = "user_product"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    sold = db.Column(db.Integer, default=0)


class UserTransaction(db.Model):
    __tablename__ = "user_transaction"
    id = db.Column(db.Integer, primary_key=True)
    items = db.Column(db.Text)  # JSON keranjang
    subtotal = db.Column(db.Float)
    discount = db.Column(db.Float)
    total = db.Column(db.Float)
    paid = db.Column(db.Float)
    change = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    kasir_name = db.Column(db.String(100))
    status = db.Column(db.String(20), default="draft")

class InvoiceTemplate(db.Model):
    __tablename__ = "invoice_template"
    user_id = db.Column(db.Integer)
    id = db.Column(db.Integer, primary_key=True)
    store_name = db.Column(db.String(100), default="EL PROJECT KASIR")
    store_address = db.Column(db.String(200), default="Jl. Mawar No. 123")
    footer_note = db.Column(db.String(200), default="Terima kasih telah berbelanja!")
    barcode_link = db.Column(db.String(300))  # tambahkan field QR Code
    show_barcode = db.Column(db.Boolean, default=True)

class UserCashier(db.Model):
    __tablename__ = "user_cashier"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    
