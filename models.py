from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# -------------------------------
# User Model
# -------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(200), nullable=False)  # hashed
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    address1 = db.Column(db.String(200))
    address2 = db.Column(db.String(200))
    note = db.Column(db.Text)
    created = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    orders = db.relationship("Order", backref="user", lazy=True)

    def __repr__(self):
        return f"<User {self.name}>"


# -------------------------------
# Product Model
# -------------------------------
class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    mrp = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    created = db.Column(db.DateTime, default=datetime.utcnow)

    # One-to-many (product can have multiple images)
    images = db.relationship("ProductImage", backref="product", lazy=True)

    def __repr__(self):
        return f"<Product {self.name}>"


# -------------------------------
# Product Images
# -------------------------------
class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(255), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    def __repr__(self):
        return f"<ProductImage {self.image_url}>"


# -------------------------------
# Orders
# -------------------------------
class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    total = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(255), nullable=False)
    note = db.Column(db.Text)
    status = db.Column(db.String(50), default="Pending")
    created = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    product = db.relationship("Product", backref="orders", lazy=True)
    payment = db.relationship("Payment", backref="order", uselist=False)

    def __repr__(self):
        return f"<Order {self.id} - User {self.user_id}>"


# -------------------------------
# Payment
# -------------------------------
class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    status = db.Column(db.String(50), default="Unpaid")  # Paid / Failed / Pending
    updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Payment {self.id} - Order {self.order_id}>"


# -------------------------------
# Banner
# -------------------------------
class Banner(db.Model):
    __tablename__ = "banners"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    image = db.Column(db.String(255), nullable=False)  # path to banner image

    def __repr__(self):
        return f"<Banner {self.name}>"
    
with app.app_context():
    db.create_all()
    print("Database tables created successfully!")