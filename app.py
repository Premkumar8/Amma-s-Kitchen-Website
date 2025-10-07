from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# -------------------------------
# App Initialization
# -------------------------------
app = Flask(__name__)
app.secret_key = 'your_super_secret_key_change_me'

# -------------------------------
# Database Config
# -------------------------------
# Make sure you have a database named 'amma' created in MySQL.
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root@localhost/ammas'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------------------
# Models
# -------------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    address1 = db.Column(db.String(200))
    address2 = db.Column(db.String(200))
    note = db.Column(db.Text)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship("Order", backref="user", lazy=True)

class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    mrp = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    
    # --- Fields added to match index.html ---
    category = db.Column(db.String(50), nullable=False) # e.g., 'masalas', 'snacks', 'dairy'
    qty = db.Column(db.String(100)) # e.g., '50g / 100g / 250g'
    rating = db.Column(db.Float, default=4.5)
    # ----------------------------------------
    
    created = db.Column(db.DateTime, default=datetime.utcnow)
    images = db.relationship("ProductImage", backref="product", lazy=True, cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="product", lazy=True)


class ProductImage(db.Model):
    __tablename__ = "product_images"
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(255), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

# NOTE: This is an unconventional cart/order model. 
# Each "Order" record with a 'Pending' status acts as a single item in the cart.
# A more robust system would use a separate Cart/OrderItem model.
class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    total = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(255))
    note = db.Column(db.Text)
    status = db.Column(db.String(50), default="Pending") # 'Pending' acts as "in cart"
    created = db.Column(db.DateTime, default=datetime.utcnow)
    payment = db.relationship("Payment", backref="order", uselist=False, cascade="all, delete-orphan")

class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    status = db.Column(db.String(50), default="Unpaid")
    updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Banner(db.Model):
    __tablename__ = "banners"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    image = db.Column(db.String(255), nullable=False)


# -------------------------------
# Helper Functions
# -------------------------------
def build_cart_context(user_id):
    """
    Builds the cart summary from 'Pending' orders for a given user.
    """
    cart_items = []
    cart_total = 0.0
    cart_count = 0
    
    pending_orders = Order.query.filter_by(user_id=user_id, status='Pending').all()
    
    for order in pending_orders:
        product = order.product
        if not product:
            continue
            
        cart_total += order.total
        cart_count += order.quantity
        
        # Get the first image, or a placeholder if none exists
        image_url = product.images[0].image_url if product.images else 'images/placeholder.svg'
        
        cart_items.append({
            'order_id': order.id,
            'product_id': product.id,
            'name': product.name,
            'qty': order.quantity,
            'price': product.price,
            'subtotal': order.total,
            'image': image_url
        })
        
    return cart_items, cart_total, cart_count

# -------------------------------
# Main Routes
# -------------------------------
@app.route('/')
def index():
    db_products = Product.query.order_by(Product.created.desc()).all()

    # Pre-process products to pass clean data to the template
    products_for_template = []
    for p in db_products:
        products_for_template.append({
            'id': p.id,
            'name': p.name,
            'qty': p.qty,
            'rating': p.rating,
            'price': p.price,
            'category': p.category,
            'image_url': p.images[0].image_url if p.images else 'images/placeholder.svg'
        })

    cart_items, cart_total, cart_count = ([], 0.0, 0)
    if 'user_id' in session:
        cart_items, cart_total, cart_count = build_cart_context(session['user_id'])
        
    return render_template(
        'index.html', 
        products=products_for_template, 
        cart_items=cart_items, 
        cart_total=cart_total, 
        cart_count=cart_count
    )

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash("Please log in to add items to your cart.", "warning")
        return redirect(url_for('login'))

    product = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))

    if quantity > product.stock:
        flash('Not enough stock available!', 'danger')
        return redirect(url_for('index'))

    user_id = session['user_id']
    
    # Check if this product is already in the user's cart (as a 'Pending' order)
    existing_order = Order.query.filter_by(user_id=user_id, product_id=product.id, status='Pending').first()
    
    if existing_order:
        # Update existing order
        existing_order.quantity += quantity
        existing_order.total = existing_order.quantity * product.price
    else:
        # Create a new order record to act as a cart item
        new_order = Order(
            user_id=user_id,
            product_id=product.id,
            quantity=quantity,
            total=quantity * product.price,
            status='Pending' # This indicates it's in the cart
        )
        db.session.add(new_order)
    
    # NOTE: Stock should ideally be reduced upon successful payment, not on cart addition.
    # This is a simplified approach.
    product.stock -= quantity
    db.session.commit()

    flash(f'"{product.name}" has been added to your cart!', 'success')
    return redirect(url_for('index'))

# -------------------------------
# Auth Routes
# -------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for('index'))
        flash("Invalid email or password.", "danger")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        
        # Check if user already exists
        if User.query.filter_by(email=email).first() or User.query.filter_by(phone=phone).first():
            flash("An account with that email or phone number already exists.", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, phone=phone, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
        
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))


# -------------------------------
# Admin / CRUD Routes (Example)
# -------------------------------
# These routes are for managing data and would typically be protected by an admin login.
# For simplicity, they are left open here.

@app.route('/admin/products')
def products_list():
    products = Product.query.all()
    return render_template('products/list.html', products=products)


@app.route('/products/add', methods=['GET', 'POST'])
def product_add():
    if request.method == 'POST':
        name = request.form['name']
        mrp = request.form['mrp']
        price = request.form['price']
        stock = request.form['stock']
        product = Product(name=name, mrp=mrp, price=price, stock=stock)
        db.session.add(product)
        db.session.commit()
        flash("Product added successfully", "success")
        return redirect(url_for('products_list'))
    return render_template('products/add.html')

@app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
def product_edit(id):
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.mrp = request.form['mrp']
        product.price = request.form['price']
        product.stock = request.form['stock']
        db.session.commit()
        flash("Product updated successfully", "success")
        return redirect(url_for('products_list'))
    return render_template('products/edit.html', product=product)

@app.route('/products/delete/<int:id>')
def product_delete(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted successfully", "success")
    return redirect(url_for('products_list'))

# -------------------------------
# Product Detail Page
# -------------------------------
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Pre-process the product for the template
    product_data = {
        'id': product.id,
        'name': product.name,
        'qty': product.qty,
        'rating': product.rating,
        'price': product.price,
        'mrp': product.mrp,
        'stock': product.stock,
        'category': product.category,
        'image_url': product.images[0].image_url if product.images else 'images/placeholder.svg'
    }

    # Fetch cart details to display in the header
    cart_items, cart_total, cart_count = ([], 0.0, 0)
    if 'user_id' in session:
        cart_items, cart_total, cart_count = build_cart_context(session['user_id'])

    return render_template(
        'product_detail.html', 
        product=product_data,
        cart_items=cart_items, 
        cart_total=cart_total, 
        cart_count=cart_count
    )

# -------------------------------
# Database Initialization & App Start
# -------------------------------
with app.app_context():
    db.create_all()
    # Check if there are any products in the database. If not, add some dummy data.
    if not Product.query.first():
        print("Database is empty. Populating with sample products...")
        
        # --- Create Sample Products ---
        products_data = [
            {'name': 'Sambar Powder', 'mrp': 70.00, 'price': 60.00, 'stock': 100, 'category': 'masalas', 'qty': '50g/100g/250g', 'rating': 4.8, 'img': 'images/prod-sambar.svg'},
            {'name': 'Rasam Powder', 'mrp': 70.00, 'price': 60.00, 'stock': 100, 'category': 'masalas', 'qty': '50g/100g/250g', 'rating': 4.7, 'img': 'images/prod-rasam.svg'},
            {'name': 'Biryani Masala', 'mrp': 80.00, 'price': 70.00, 'stock': 80, 'category': 'masalas', 'qty': '50g/100g', 'rating': 4.9, 'img': 'images/prod-biryani.svg'},
            {'name': 'Sweet Paniyaram', 'mrp': 130.00, 'price': 120.00, 'stock': 50, 'category': 'snacks', 'qty': '1 Unit', 'rating': 4.6, 'img': 'images/prod-paniyaram.svg'},
            {'name': 'Murukku', 'mrp': 120.00, 'price': 110.00, 'stock': 60, 'category': 'snacks', 'qty': '1 Unit', 'rating': 4.8, 'img': 'images/prod-murukku.svg'},
            {'name': 'Homemade Ghee', 'mrp': 380.00, 'price': 350.00, 'stock': 40, 'category': 'dairy', 'qty': '500ml', 'rating': 5.0, 'img': 'images/prod-ghee.svg'},
            {'name': 'Fresh Curd', 'mrp': 50.00, 'price': 40.00, 'stock': 70, 'category': 'dairy', 'qty': '1 Unit', 'rating': 4.5, 'img': 'images/prod-curd.svg'},
            {'name': 'Dosa Mix', 'mrp': 100.00, 'price': 90.00, 'stock': 90, 'category': 'dosa', 'qty': '1kg', 'rating': 4.6, 'img': 'images/prod-dosa-mix.svg'},
            {'name': 'Masoor Dal', 'mrp': 100.00, 'price': 90.00, 'stock': 120, 'category': 'dhall', 'qty': '1kg', 'rating': 4.4, 'img': 'images/prod-masoor.svg'}
        ]

        for data in products_data:
            new_prod = Product(name=data['name'], mrp=data['mrp'], price=data['price'], stock=data['stock'], category=data['category'], qty=data['qty'], rating=data['rating'])
            db.session.add(new_prod)
            db.session.commit() # Commit to get the product ID
            
            # Add image for the product
            new_img = ProductImage(image_url=data['img'], product_id=new_prod.id)
            db.session.add(new_img)
        
        db.session.commit()
        print("Sample products added successfully!")

if __name__ == '__main__':
    app.run(debug=True)