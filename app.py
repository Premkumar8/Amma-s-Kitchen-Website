from functools import wraps
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash, make_response
from werkzeug.security import check_password_hash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from flask_migrate import Migrate
import json
import razorpay
from sqlalchemy import func, desc
from werkzeug.utils import secure_filename
# ===== CHATBOT IMPORTS =====
import os
import google.generativeai as genai  # <--- NEW LIBRARY
import uuid
from functools import lru_cache
import os
import csv
from io import StringIO

# 👇 ADD THESE TWO LINES HERE
from dotenv import load_dotenv
load_dotenv()  # This loads the variables from .env

# Initialize OpenAI client
# 👇 Ensure this line is strictly after load_dotenv()
# Configure Google Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
# Initialize OpenAI client
model = genai.GenerativeModel('gemini-2.5-flash')

conversations = {}
# ===== END CHATBOT IMPORTS =====

# -------------------------------
# App Initialization
# -------------------------------
app = Flask(__name__)
app.secret_key = 'your_super_secret_key_change_me'
# -------------------------------
# Database Config
# -------------------------------
# Make sure you have a database named 'amma' created in MySQL.
#app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root@localhost/ammas'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:password@db:5432/ammas_kitchen'
#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://ammaskitchen_user:7gL0eP48duTTG8ccRfyUWrYsJMo4PuP8@dpg-d3uvp4v5r7bs73frfnmg-a:5432/ammaskitchen'

#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:WelComeSai08@948@db:5432/ammas_kitchen'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

migrate = Migrate(app, db)
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
    is_admin = db.Column(db.Boolean, default=False) 
    orders = db.relationship("Order", backref="user", lazy=True)

class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    mrp = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    ingredients = db.Column(db.String(500), nullable=True)
    best_with = db.Column(db.String(500), nullable=True)
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

# --- NEW CONTACT MODEL ---
class Contact(db.Model):
    __tablename__ = "contacts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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


def process_products(items):
    """Formats database product objects into a dictionary for the template."""
    result = []
    for p in items:
        # Use first image or placeholder
        image_url = p.images[0].image_url if p.images else 'images/placeholder.svg'
        result.append({
            'id': p.id,
            'name': p.name,
            'qty': p.qty,
            'rating': p.rating,
            'price': p.price,
            'category': p.category,
            'stock': p.stock,  # Added stock info
            'image_url': image_url
        })
    return result

# ADMIN DECORATOR
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access the admin panel.", "warning")
            return redirect(url_for('admin_login'))  # <--- CHANGED THIS
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash("Access denied. Admin privileges required.", "danger")
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if 'user_id' in session:
#         return redirect(url_for('index'))
        
#     if request.method == 'POST':
#         email = request.form['email']
#         password = request.form['password']
        
#         user = User.query.filter_by(email=email).first()
        
#         # 🔒 SECURE CHECK: verify the hash instead of plain text
#         if user and check_password_hash(user.password, password):
#             session['user_id'] = user.id
#             session['user_name'] = user.name
#             flash(f"Welcome back, {user.name}!", "success")
#             return redirect(url_for('index'))
#         else:
#             flash("Invalid email or password.", "danger")
            
#     return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, don't show login page
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            # Login Success: Set Session Variables
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['is_admin'] = user.is_admin
            
            flash('Login successful!', 'success')
            
            # ---------------------------------------------------------
            # SMART REDIRECT LOGIC
            # ---------------------------------------------------------
            # Check if there is a specific page they wanted to visit
            next_page = session.pop('next_url', None) # Get and delete from session
            
            if next_page:
                return redirect(next_page) # Go to Checkout (or other saved page)
            else:
                return redirect(url_for('index')) # Default to Home
            # ---------------------------------------------------------
            
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
            
    return render_template('login.html')

# --- ADD THIS AT THE VERY TOP OF APP.PY ---
PER_PAGE = 12

@app.route('/')
def index():
    # Get current page, default to 1
    page = request.args.get('page', 1, type=int)
    
    # Fetch products for THIS page
    db_products = Product.query.order_by(
        Product.created.desc(), 
        Product.id.desc()
    ).paginate(page=page, per_page=PER_PAGE, error_out=False)
    
    # Format products
    products_for_template = process_products(db_products.items)
    
    # Calculate next page number (e.g., if we are on 1, next is 2)
    next_page_num = (page + 1) if db_products.has_next else None

    # ... (Keep your existing Cart Logic here) ...
    cart_items, cart_total, cart_count = ([], 0.0, 0)
    if 'user_id' in session:
        cart_items, cart_total, cart_count = build_cart_context(session['user_id'])
    
    return render_template(
        'index.html',
        products=products_for_template,
        next_page=next_page_num,  # Pass '2' to the template
        has_next=db_products.has_next,
        cart_items=cart_items,
        cart_total=cart_total,
        cart_count=cart_count
    )

@app.route('/load-products')
def load_products():
    # 1. Get the page number requested by the button (e.g., 2, 3...)
    # We do NOT default to 2 here anymore. We rely on the button.
    page = request.args.get('page', type=int)
    
    # 2. Query the Database for THAT SPECIFIC page
    db_products = Product.query.order_by(
        Product.created.desc(), 
        Product.id.desc()
    ).paginate(page=page, per_page=PER_PAGE, error_out=False)
    
    # 3. Format products
    products_for_template = process_products(db_products.items)
    
    # 4. Calculate the NEXT page (e.g., if we loaded 2, next is 3)
    next_page_num = (page + 1) if db_products.has_next else None
    
    # 5. Return only the cards
    return render_template(
        '_product_cards.html', 
        products=products_for_template,
        next_page=next_page_num
    )
    
@app.route('/search')
def search():
    query = request.args.get('q', '')
    # Example: search by product name (case-insensitive)
    results = []
    if query:
        results = Product.query.filter(Product.name.ilike(f"%{query}%")).limit(50).all()
    return render_template('search_results.html', results=results, query=query)

@app.route('/search-suggest')
def search_suggest():
    term = request.args.get('q', '').strip()
    if not term:
        return jsonify([])
    results = Product.query.with_entities(Product.id, Product.name).filter(
        Product.name.ilike(f'%{term}%')
    ).limit(10).all()
    return jsonify([{'id': p.id, 'name': p.name} for p in results])

# @app.route('/profile')
# def profile():
#     # Assumes user info in session; pass to template if needed
#     return render_template('profile.html')

@app.route('/profile')
def profile():
    user_id = session.get('user_id')

    user = User.query.get(user_id)
    orders = Order.query.filter_by(user_id=user_id).order_by(Order.created.desc()).all()
    enriched_orders = []
    for order in orders:
        product = Product.query.get(order.product_id)
        payment = Payment.query.filter_by(order_id=order.id).first()
        enriched_orders.append({
            "order": order,
            "product": product,
            "payment": payment
        })

    return render_template(
        'profile.html',
        user=user,
        orders=enriched_orders
    )

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    user.name = request.form['name']
    user.email = request.form['email']
    user.phone = request.form['phone']
    user.address1 = request.form['address1']
    user.address2 = request.form['address2']
    user.note = request.form['note']
    db.session.commit()
    print("Address1", user.address1)
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))


@app.route('/google-login')
def google_login():
    # placeholder for Google OAuth; you can redirect to a real OAuth handler here
    return "Google login coming soon!"

@app.route('/cancel_order/<int:order_id>', methods=['POST'])
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status == "Pending":
        order.status = "Cancelled"
        db.session.commit()
        flash("Order cancelled.", "success")
    else:
        flash("Order cannot be cancelled.", "danger")
    return redirect(url_for('profile'))

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

# 2. Update the Category Route
@app.route('/category/<category_name>')
def category_products(category_name):
    # Retrieve products matching the category
    # Added order_by to keep it consistent
    db_products = Product.query.filter_by(category=category_name).order_by(Product.created.desc()).all()
    
    products_for_template = process_products(db_products)
    
    # Find the maximum price in this category to set the slider range dynamically
    max_price = 0
    if products_for_template:
        max_price = max(p['price'] for p in products_for_template)
    
    return render_template(
        'category_products.html', 
        products=products_for_template, 
        category=category_name,
        max_price_limit=max_price
    )

@app.route('/products')
def products_list_1():
    # 1. Get Query Parameters
    page = int(request.args.get('page', 1))
    min_price = request.args.get('min_price', 0, type=int)
    max_price = request.args.get('max_price', 10000, type=int)
    in_stock = request.args.get('stock') == 'true'
    selected_categories = request.args.getlist('category') 
    sort_by = request.args.get('sort', 'newest')

    # 2. Base Query
    query = Product.query

    # 3. Apply Filters
    if selected_categories:
        query = query.filter(Product.category.in_(selected_categories))
    
    if max_price:
        query = query.filter(Product.price <= max_price)
        query = query.filter(Product.price >= min_price)
    
    if in_stock:
        query = query.filter(Product.stock > 0)

    # 4. Apply Sorting
    if sort_by == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_high':
        query = query.order_by(Product.price.desc())
    else: # Default newest
        query = query.order_by(Product.created.desc(), Product.id.desc())

    # 5. Pagination
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    products_data = process_products(pagination.items)

    # 6. Sidebar Data
    all_categories = [r[0] for r in db.session.query(Product.category).distinct().all()]
    global_max_price = db.session.query(func.max(Product.price)).scalar() or 1000

    # ---------------------------------------------------------
    # 7. CART CONTEXT (Added this to fix the issue)
    # ---------------------------------------------------------
    cart_items, cart_total, cart_count = ([], 0.0, 0)
    if 'user_id' in session:
        cart_items, cart_total, cart_count = build_cart_context(session['user_id'])
    # ---------------------------------------------------------

    # 8. Handle AJAX (Partial Update)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('_product_grid_partial.html', 
                               products=products_data, 
                               pagination=pagination)

    # 9. Full Page Load
    return render_template('products.html', 
                           products=products_data, 
                           pagination=pagination,
                           all_categories=all_categories,
                           global_max_price=global_max_price,
                           # Pass Cart Data to Template
                           cart_items=cart_items,
                           cart_total=cart_total,
                           cart_count=cart_count,
                           current_filters={
                               'max': max_price, 
                               'cats': selected_categories, 
                               'stock': in_stock,
                               'sort': sort_by
                           })
     
@app.route('/category/<category_name>')
def show_category(category_name):
    # Retrieve products matching the category
    db_products = Product.query.filter_by(category=category_name).order_by(Product.created.desc()).all()
    
    # Process products with their primary images for the template
    products_for_template = []
    for p in db_products:
        # Use the first image or a default placeholder
        image_url = p.images[0].image_url if p.images else 'images/placeholder.svg'
        products_for_template.append({
            'id': p.id,
            'name': p.name,
            'qty': p.qty,
            'rating': p.rating,
            'price': p.price,
            'stock': p.stock,  # Add this if you display it
            'category': p.category,
            'image_url': image_url
        })
    
    return render_template(
        'category_products.html',
        products=products_for_template,
        category=category_name
    )
    
# -------------------------------
# Checkout
# -------------------------------


#api_key = razorpay.Client(auth=("YOUR_KEY_ID", "YOUR_KEY_SECRET"))

import razorpay
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import json

razorpay_client = razorpay.Client(auth=("YOUR_KEY_ID", "YOUR_KEY_SECRET"))

@app.route('/checkout', methods=['GET'])
def checkout():
    # 1. Login Check
    if 'user_id' not in session:
        session['next_url'] = url_for('checkout')
        flash("Please login to proceed with checkout.", "warning")
        return redirect(url_for('login'))
    
    # 2. Pass the Key ID to the template for the frontend script
    return render_template('checkout.html', key_id="YOUR_KEY_ID")

@app.route("/create_order", methods=["POST"])
def create_order():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # Get amount from frontend
        data = request.get_json()
        amount = float(data['amount'])
        
        # Razorpay expects amount in paise (multiply by 100)
        amount_paise = int(amount * 100)
        
        # Create Order
        order_data = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"order_rcptid_{session['user_id']}_{int(datetime.now().timestamp())}",
            "payment_capture": 1 # Auto capture
        }
        
        order = razorpay_client.order.create(data=order_data)
        return jsonify(order)
        
    except Exception as e:
        print(f"Error creating order: {e}")
        return jsonify({'error': 'Something went wrong'}), 500

@app.route("/verify_payment", methods=["POST"])
def verify_payment():
    if 'user_id' not in session:
        return jsonify({'status': 'failed'}), 401

    data = request.get_json()
    
    try:
        # 1. Verify Signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
        
        # 2. Payment Verified - Now Save to Database
        cart_data = data.get('cart_data', {})
        user_id = session['user_id']
        
        # Example saving logic (Adjust to your exact Order model fields)
        # for item_key, item in cart_data.items():
        #     new_order = Order(
        #         user_id=user_id,
        #         product_id=item['id'], # Ensure your cart has 'id'
        #         quantity=item['quantity'],
        #         total=item['price'] * item['quantity'],
        #         status="Paid", # Or 'Pending' -> 'Paid'
        #         address="User Address Here" # Pass address from frontend if needed
        #     )
        #     db.session.add(new_order)
        #     # Create Payment Record
        #     new_payment = Payment(order=new_order, status="Success")
        #     db.session.add(new_payment)
        
        # db.session.commit()

        return jsonify({'status': 'success'})
        
    except razorpay.errors.SignatureVerificationError:
        return jsonify({'status': 'failed', 'message': 'Signature Verification Failed'})
    except Exception as e:
        print(f"Payment Error: {e}")
        return jsonify({'status': 'failed', 'message': str(e)})
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        is_admin = False
        # Check if user already exists
        if User.query.filter_by(email=email).first() or User.query.filter_by(phone=phone).first():
            flash("An account with that email or phone number already exists.", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, phone=phone, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash("Registration successful!", "success")
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
    return render_template('admin/products.html', products=products)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    # 1. Handle Form Submission
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        # Store in DB
        new_contact = Contact(name=name, email=email, subject=subject, message=message)
        db.session.add(new_contact)
        db.session.commit()
        
        flash(f"Thank you, {name}! Your message has been submitted successfully. We will contact you shortly.", "success")
        # Redirect to the page BUT append the anchor ID to scroll down automatically
        return redirect(url_for('contact') + '#contact-area')

    # 2. Standard Page Load (Cart Logic)
    cart_items, cart_total, cart_count = ([], 0.0, 0)
    if 'user_id' in session:
        cart_items, cart_total, cart_count = build_cart_context(session['user_id'])
        
    return render_template('contact.html', cart_items=cart_items, cart_total=cart_total, cart_count=cart_count)

@app.route('/terms', methods=['GET', 'POST'])
def terms():
    return render_template('terms.html')

@app.route('/privacy', methods=['GET', 'POST'])
def privacy():
    return render_template('privacy.html')

@app.route('/shipping', methods=['GET', 'POST'])
def shipping():
    return render_template('shipping.html')

@app.route('/refund', methods=['GET', 'POST'])
def refund():
    return render_template('refund.html')

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

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)

    # Collect product images for gallery
    images = [
        {'url': img.image_url}
        for img in product.images
    ] if product.images else [{'url': 'images/placeholder.svg'}]

    # Add a description if your Product model supports it; else use a default
    product_data = {
        'id': product.id,
        'name': product.name,
        'qty': product.qty,
        'rating': product.rating,
        'price': product.price,
        'mrp': product.mrp,
        'stock': product.stock,
        'category': product.category,
        'ingredients': [ing.strip() for ing in product.ingredients.split(',')] if product.ingredients else [],
        'suggested_uses': [use.strip() for use in product.best_with.split(',')] if hasattr(product, 'best_with') and product.best_with else [],
        'description': getattr(product, 'description', ''),  # add this if your model supports!
        'images': images
    }

    # Example recommendations (pick random or similar products)
    recommendations = Product.query.filter(Product.id != product.id).limit(4).all()
    recommendation_data = [
        {
            'id': rec.id,
            'name': rec.name,
            'image_url': rec.images[0].image_url if rec.images else 'images/placeholder.svg',
            'price': rec.price
        }
        for rec in recommendations
    ]

    # Fetch cart details to display in the header
    cart_items, cart_total, cart_count = ([], 0.0, 0)
    if 'user_id' in session:
        cart_items, cart_total, cart_count = build_cart_context(session['user_id'])

    return render_template(
        'product_detail.html',
        product=product_data,
        recommendations=recommendation_data,
        cart_items=cart_items,
        cart_total=cart_total,
        cart_count=cart_count
    )

# -------------------------------
# Database Initialization & App Start
# -------------------------------
with app.app_context():
    db.create_all()
    # 1. Create Default Admin User if not exists
    admin_email = "admin@ammaskitchen.com"
    if not User.query.filter_by(email=admin_email).first():
        print(f"Creating admin user: {admin_email} ...")
        
        # Create secure hash for 'admin123'
        hashed_pw = generate_password_hash("admin123")
        
        admin = User(
            name="System Admin", 
            email=admin_email, 
            phone="9999999999", 
            password=hashed_pw, 
            is_admin=True, # <--- Crucial: Sets this user as Admin
            address1="Admin HQ",
            address2="Server Room"
        )
        
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin account created!")
        print(f"   Email: {admin_email}")
        print("   Pass : admin123")
    else:
        print("ℹ️  Admin account already exists.")
    # Check if there are any products in the database. If not, add some dummy data.
    # if not Product.query.first():
    #     print("Database is empty. Populating with sample products...")
        
    #     # --- Create Sample Products ---
    #     products_data = [
    #         {'name': 'Sambar Powder', 'mrp': 70.00, 'price': 60.00, 'stock': 100, 'category': 'masalas', 'qty': '50g/100g/250g', 'rating': 4.8, 'img': 'images/prod-sambar.svg'},
    #         {'name': 'Rasam Powder', 'mrp': 70.00, 'price': 60.00, 'stock': 100, 'category': 'masalas', 'qty': '50g/100g/250g', 'rating': 4.7, 'img': 'images/prod-rasam.svg'},
    #         {'name': 'Biryani Masala', 'mrp': 80.00, 'price': 70.00, 'stock': 80, 'category': 'masalas', 'qty': '50g/100g', 'rating': 4.9, 'img': 'images/prod-biryani.svg'},
    #         {'name': 'Sweet Paniyaram', 'mrp': 130.00, 'price': 120.00, 'stock': 50, 'category': 'snacks', 'qty': '1 Unit', 'rating': 4.6, 'img': 'images/prod-paniyaram.svg'},
    #         {'name': 'Murukku', 'mrp': 120.00, 'price': 110.00, 'stock': 60, 'category': 'snacks', 'qty': '1 Unit', 'rating': 4.8, 'img': 'images/prod-murukku.svg'},
    #         {'name': 'Homemade Ghee', 'mrp': 380.00, 'price': 350.00, 'stock': 40, 'category': 'dairy', 'qty': '500ml', 'rating': 5.0, 'img': 'images/prod-ghee.svg'},
    #         {'name': 'Fresh Curd', 'mrp': 50.00, 'price': 40.00, 'stock': 70, 'category': 'dairy', 'qty': '1 Unit', 'rating': 4.5, 'img': 'images/prod-curd.svg'},
    #         {'name': 'Dosa Mix', 'mrp': 100.00, 'price': 90.00, 'stock': 90, 'category': 'dosa', 'qty': '1kg', 'rating': 4.6, 'img': 'images/prod-dosa-mix.svg'},
    #         {'name': 'Masoor Dal', 'mrp': 100.00, 'price': 90.00, 'stock': 120, 'category': 'dhall', 'qty': '1kg', 'rating': 4.4, 'img': 'images/prod-masoor.svg'}
    #     ]

    #     for data in products_data:
    #         new_prod = Product(name=data['name'], mrp=data['mrp'], price=data['price'], stock=data['stock'], category=data['category'], qty=data['qty'], rating=data['rating'])
    #         db.session.add(new_prod)
    #         db.session.commit() # Commit to get the product ID
            
    #         # Add image for the product
    #         new_img = ProductImage(image_url=data['img'], product_id=new_prod.id)
    #         db.session.add(new_img)
        
    #     db.session.commit()
    #     print("Sample products added successfully!")

# -------------------------------
# ADMIN ROUTES
# -------------------------------
# 2. NEW ADMIN LOGIN ROUTE
@app.route('/administrator/login', methods=['GET', 'POST'])
def admin_login():
    # If already logged in as admin, go to dashboard
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.is_admin:
            return redirect(url_for('admin_dashboard'))
        elif user:
            flash("You are logged in as a customer. Please logout to access Admin.", "warning")
            return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        # Check password AND is_admin flag
        if user and user.is_admin and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash(f"Welcome back, Admin {user.name}!", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid credentials or not an administrator.", "danger")
            
    return render_template('admin/login.html')

# @app.route('/admin')
# @admin_required
# def admin_dashboard():
#     # Define Finalized Statuses for accurate business metrics
#     finalized_statuses = ['Shipped', 'Delivered']
#     all_statuses = ['Cancelled', 'Shipped', 'Delivered', 'Pending']

#     total_sales = db.session.query(func.sum(Order.total)).filter(
#         Order.status.in_(finalized_statuses)
#     ).scalar() or 0
#     total_orders = Order.query.filter(
#         Order.status.in_(all_statuses)
#     ).count()
    
#     total_products = Product.query.count()
#     total_customers = User.query.filter_by(is_admin=False).count()
    
#     page = request.args.get('page', 1, type=int)
#     per_page = 5

#     recent_orders = Order.query.filter(
#         Order.status.in_(all_statuses)
#     ).order_by(Order.created.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
#     return render_template('admin/dashboard.html', 
#                            total_sales=total_sales,
#                            total_orders=total_orders,
#                            total_products=total_products,
#                            total_customers=total_customers,
#                            recent_orders=recent_orders) # Passes the Pagination object, not a list

@app.route('/admin/export_csv')
@admin_required
def export_csv():
    import csv
    from io import StringIO
    from flask import make_response

    # 1. Get arguments
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    
    print(f"DEBUG CSV: Received Start: {start_str}, End: {end_str}") # Check your terminal

    query = Order.query

    # 2. Apply Date Filter
    if start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d')
            # Add 1 day to end_date to include the whole day (e.g., up to 23:59:59)
            end_date = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)
            
            query = query.filter(Order.created >= start_date, Order.created < end_date)
        except ValueError as e:
            print(f"DEBUG CSV Error: Date format issue - {e}")

    # 3. Fetch Data (Eager load user to prevent detachment errors)
    orders = query.order_by(Order.created.desc()).all()
    
    print(f"DEBUG CSV: Found {len(orders)} orders to export.") # Check if this is 0

    # 4. Generate CSV
    si = StringIO()
    cw = csv.writer(si)
    
    # Header
    cw.writerow(['Order ID', 'Date', 'Customer Name', 'Email', 'Address', 'Status', 'Total Amount'])
    
    # Rows
    for order in orders:
        # Handle cases where user might be deleted (Optional safety)
        u_name = order.user.name if order.user else "Unknown"
        u_email = order.user.email if order.user else "Unknown"
        
        cw.writerow([
            order.id, 
            order.created.strftime('%Y-%m-%d %H:%M'), 
            u_name,
            u_email,
            order.address, 
            order.status, 
            order.total
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=sales_report.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/admin')
@admin_required
def admin_dashboard():
    # ---------------------------------------------------------
    # 1. SETUP & CONSTANTS
    # ---------------------------------------------------------
    finalized_statuses = ['Shipped', 'Delivered']  # For Revenue & Top Products
    all_statuses = ['Cancelled', 'Shipped', 'Delivered', 'Pending'] # For Counts
    
    today = datetime.now().date()

    # ---------------------------------------------------------
    # 2. OVERVIEW CARDS
    # ---------------------------------------------------------
    total_sales = db.session.query(func.sum(Order.total)).filter(
        Order.status.in_(finalized_statuses)
    ).scalar() or 0
    
    total_orders = Order.query.filter(Order.status.in_(all_statuses)).count()
    total_products = Product.query.count()
    total_customers = User.query.filter_by(is_admin=False).count()

    # ---------------------------------------------------------
    # 3. CHART 1: REVENUE (Line Chart)
    # ---------------------------------------------------------
    # A. Daily (Last 7 Days)
    daily_labels = []
    daily_values = []
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        day_total = db.session.query(func.sum(Order.total))\
            .filter(func.date(Order.created) == target_date)\
            .filter(Order.status.in_(finalized_statuses))\
            .scalar() or 0
        daily_labels.append(target_date.strftime('%a')) # Mon, Tue
        daily_values.append(float(day_total))

    # B. Monthly (Last 12 Months)
    monthly_labels = []
    monthly_values = []
    for i in range(11, -1, -1):
        date_cursor = today.replace(day=1) - timedelta(days=i*30)
        month_total = db.session.query(func.sum(Order.total))\
            .filter(func.extract('month', Order.created) == date_cursor.month)\
            .filter(func.extract('year', Order.created) == date_cursor.year)\
            .filter(Order.status.in_(finalized_statuses))\
            .scalar() or 0
        monthly_labels.append(date_cursor.strftime('%b')) # Jan, Feb
        monthly_values.append(float(month_total))

    # C. Yearly (Last 5 Years)
    yearly_labels = []
    yearly_values = []
    for i in range(4, -1, -1):
        target_year = today.year - i
        year_total = db.session.query(func.sum(Order.total))\
            .filter(func.extract('year', Order.created) == target_year)\
            .filter(Order.status.in_(finalized_statuses))\
            .scalar() or 0
        yearly_labels.append(str(target_year))
        yearly_values.append(float(year_total))

    # ---------------------------------------------------------
    # 4. CHART 2: ORDER STATUS (Doughnut Chart)
    # ---------------------------------------------------------
    def get_status_data(start_date):
        results = db.session.query(Order.status, func.count(Order.id))\
            .filter(Order.created >= start_date)\
            .group_by(Order.status).all()
        labels = [r[0] for r in results]
        data = [r[1] for r in results]
        return labels, data

    daily_status_labels, daily_status_data = get_status_data(today)
    monthly_status_labels, monthly_status_data = get_status_data(today - timedelta(days=30))
    yearly_status_labels, yearly_status_data = get_status_data(today - timedelta(days=365))

    # ---------------------------------------------------------
    # 5. CHART 3: TOP PRODUCTS (Bar Chart)
    # ---------------------------------------------------------
    # Logic: Join Order directly to Product (No OrderItem table)
    def get_top_products(start_date):
        return db.session.query(Product.name, func.sum(Order.quantity))\
            .join(Product, Product.id == Order.product_id)\
            .filter(Order.created >= start_date)\
            .filter(Order.status.in_(finalized_statuses))\
            .group_by(Product.name)\
            .order_by(desc(func.sum(Order.quantity)))\
            .limit(5).all()

    # Fetch Data
    d_top = get_top_products(today)
    daily_prod_names = [p[0] for p in d_top]
    daily_prod_counts = [int(p[1]) for p in d_top]

    m_top = get_top_products(today - timedelta(days=30))
    monthly_prod_names = [p[0] for p in m_top]
    monthly_prod_counts = [int(p[1]) for p in m_top]

    y_top = get_top_products(today - timedelta(days=365))
    yearly_prod_names = [p[0] for p in y_top]
    yearly_prod_counts = [int(p[1]) for p in y_top]

    # ---------------------------------------------------------
    # 6. TABLE A: RECENT ORDERS (Standard Pagination)
    # ---------------------------------------------------------
    page = request.args.get('page', 1, type=int)
    recent_orders = Order.query.filter(Order.status.in_(all_statuses))\
        .order_by(Order.created.desc())\
        .paginate(page=page, per_page=10, error_out=False)

    # ---------------------------------------------------------
    # 7. TABLE B: ORDER REPORT (Date Filter + Separate Pagination)
    # ---------------------------------------------------------
    report_start = request.args.get('report_start')
    report_end = request.args.get('report_end')
    
    report_query = Order.query.order_by(Order.created.desc())
    
    if report_start and report_end:
        # Filter by specific range
        try:
            s_date = datetime.strptime(report_start, '%Y-%m-%d')
            e_date = datetime.strptime(report_end, '%Y-%m-%d') + timedelta(days=1)
            report_query = report_query.filter(Order.created >= s_date, Order.created < e_date)
        except ValueError:
            pass # Invalid date format, ignore
    else:
        # Default: Show Today's orders to keep page load fast
        s_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        report_query = report_query.filter(Order.created >= s_date)

    report_page = request.args.get('report_page', 1, type=int)
    report_orders = report_query.paginate(page=report_page, per_page=20, error_out=False)

    # ---------------------------------------------------------
    # 8. RENDER TEMPLATE
    # ---------------------------------------------------------
    return render_template('admin/dashboard.html', 
        # Overview Cards
        total_sales=total_sales, 
        total_orders=total_orders,
        total_products=total_products, 
        total_customers=total_customers,
        
        # Recent Orders Table
        recent_orders=recent_orders,

        # Report Table
        report_orders=report_orders,
        report_start=report_start,
        report_end=report_end,

        # Chart 1: Revenue
        daily_labels=daily_labels, daily_values=daily_values,
        monthly_labels=monthly_labels, monthly_values=monthly_values,
        yearly_labels=yearly_labels, yearly_values=yearly_values,
        
        # Chart 2: Status
        daily_status_labels=daily_status_labels, daily_status_data=daily_status_data,
        monthly_status_labels=monthly_status_labels, monthly_status_data=monthly_status_data,
        yearly_status_labels=yearly_status_labels, yearly_status_data=yearly_status_data,
        
        # Chart 3: Top Products
        daily_prod_names=daily_prod_names, daily_prod_counts=daily_prod_counts,
        monthly_prod_names=monthly_prod_names, monthly_prod_counts=monthly_prod_counts,
        yearly_prod_names=yearly_prod_names, yearly_prod_counts=yearly_prod_counts
    )

UPLOAD_FOLDER = 'static/images/products'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/admin/products')
@admin_required
def admin_products():
    products = Product.query.order_by(Product.id.desc()).all()
    return render_template('admin/products.html', products=products)

@app.route('/admin/product/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        mrp = float(request.form['mrp'])
        stock = int(request.form['stock'])
        category = request.form['category']
        qty = request.form['qty']
        
        # 1. Create Product and Commit (to get ID)
        new_product = Product(name=name, price=price, mrp=mrp, stock=stock, category=category, qty=qty)
        db.session.add(new_product)
        db.session.commit() # Commit 1: Generates new_product.id
        
        # --- Multi-Image Handling ---
        files = request.files.getlist('image')
        for file in files:
            if file and file.filename != '':
                filename = secure_filename(f"{new_product.id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
                new_image = ProductImage(image_url=f'images/products/{filename}', product_id=new_product.id)
                db.session.add(new_image) # Add to session, but DO NOT commit yet
        
        # 2. Commit all image records in one transaction
        db.session.commit() # <--- FIXED: This final commit saves all images to the DB
        
        flash("Product added successfully!", "success")
        return redirect(url_for('admin_products'))
        
    return render_template('admin/product_add.html')

# @app.route('/admin/product/edit/<int:id>', methods=['GET', 'POST'])
# @admin_required
# def admin_edit_product(id):
#     product = Product.query.get_or_404(id)
    
#     if request.method == 'POST':
#         # 1. Update Basic Fields
#         product.name = request.form['name']
#         product.price = float(request.form['price'])
#         product.mrp = float(request.form['mrp'])
#         product.stock = int(request.form['stock'])
#         product.category = request.form['category']
#         product.qty = request.form['qty']
        
#         # 2. Handle Image Upload (APPEND NEW IMAGES)
#         files = request.files.getlist('image') # Gets a list of all files
#         for file in files:
#             if file and file.filename != '':
#                 # Create a unique filename using product ID and microsecond timestamp
#                 timestamp_suffix = datetime.now().strftime('%f')
#                 filename = secure_filename(f"{product.id}_{timestamp_suffix}_{file.filename}")
#                 file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
#                 # Append NEW image record to the product's gallery
#                 new_image = ProductImage(
#                     image_url=f'images/products/{filename}', 
#                     product_id=product.id
#                 )
#                 db.session.add(new_image)
        
#         db.session.commit()
#         flash("Product updated successfully!", "success")
#         return redirect(url_for('admin_products'))
        
#     return render_template('admin/product_edit.html', product=product)

@app.route('/admin/product/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(id):
    product = Product.query.get_or_404(id)
    
    if request.method == 'POST':
        # Update Basic Fields
        product.name = request.form['name']
        product.price = float(request.form['price'])
        product.mrp = float(request.form['mrp'])
        product.stock = int(request.form['stock'])
        product.category = request.form['category']
        product.qty = request.form['qty']
        
        # --- NEW LINES ADDED HERE ---
        product.ingredients = request.form.get('ingredients')
        product.best_with = request.form.get('best_with')
        # -----------------------------
        
        # Handle Image Upload (Append)
        files = request.files.getlist('image')
        for file in files:
            if file and file.filename != '':
                timestamp_suffix = datetime.now().strftime('%f')
                filename = secure_filename(f"{product.id}_{timestamp_suffix}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
                new_image = ProductImage(image_url=f'images/products/{filename}', product_id=product.id)
                db.session.add(new_image)
        
        db.session.commit()
        flash("Product updated successfully!", "success")
        return redirect(url_for('admin_products'))
        
    # GET request renders template
    return render_template('admin/product_edit.html', product=product)

@app.route('/admin/product/delete/<int:id>')
@admin_required
def admin_delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted.", "success")
    return redirect(url_for('admin_products'))

@app.route('/admin/image/delete/<int:image_id>', methods=['POST'])
@admin_required
def admin_delete_image(image_id):
    # 1. Find the image record
    image = ProductImage.query.get_or_404(image_id)
    
    # 2. Get the parent product ID for redirection later
    product_id = image.product_id
    
    # 3. Optional: Delete the file from the server disk (Good practice)
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image.image_url.split('/')[-1])
    if os.path.exists(image_path):
        os.remove(image_path)
    
    # 4. Delete the database record
    db.session.delete(image)
    db.session.commit()
    
    flash("Image removed successfully.", "success")
    # Redirect back to the product edit page
    return redirect(url_for('admin_edit_product', id=product_id))

# @app.route('/admin/products', methods=['GET', 'POST'])
# @admin_required
# def admin_products():
#     if request.method == 'POST':
#         name = request.form['name']
#         price = float(request.form['price'])
#         mrp = float(request.form['mrp'])
#         stock = int(request.form['stock'])
#         category = request.form['category']
#         qty = request.form['qty']
        
#         new_product = Product(name=name, price=price, mrp=mrp, stock=stock, category=category, qty=qty)
#         db.session.add(new_product)
#         db.session.commit()
#         flash("Product added successfully!", "success")
#         return redirect(url_for('admin_products'))
        
#     products = Product.query.order_by(Product.id.desc()).all()
#     return render_template('admin/products.html', products=products)

# @app.route('/admin/product/delete/<int:id>')
# @admin_required
# def admin_delete_product(id):
#     product = Product.query.get_or_404(id)
#     db.session.delete(product)
#     db.session.commit()
#     flash("Product deleted.", "success")
#     return redirect(url_for('admin_products'))

@app.route('/admin/orders')
@admin_required
def admin_orders():
    # Include all statuses for admin view, but fetch only one page.
    finalized_statuses = ['Shipped', 'Delivered', 'Cancelled']
    
    page = request.args.get('page', 1, type=int)
    per_page = 5  # Set items per page

    # Filter out *only* temporary/unnecessary statuses if needed, otherwise query all.
    # We will query ALL orders and rely on the UI to filter what it shows/manages.
    orders_query = Order.query 
    
    orders_pagination = orders_query.order_by(Order.created.desc()).paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    return render_template('admin/orders.html', 
                           orders=orders_pagination.items, 
                           pagination=orders_pagination) # Pass the full object
    
# @app.route('/admin/orders')
# @admin_required
# def admin_orders():
#     # Include all statuses for admin view, but fetch only one page.
#     finalized_statuses = ['Shipped', 'Delivered', 'Cancelled', 'Pending']
    
#     page = request.args.get('page', 1, type=int)
#     per_page = 20  # Set items per page

#     # Filter out *only* temporary/unnecessary statuses if needed, otherwise query all.
#     # We will query ALL orders and rely on the UI to filter what it shows/manages.
#     orders_query = Order.query 
    
#     orders_pagination = orders_query.order_by(Order.created.desc()).paginate(
#         page=page, 
#         per_page=per_page, 
#         error_out=False
#     )
    
#     return render_template('admin/orders.html', 
#                            orders=orders_pagination.items, 
#                            pagination=orders_pagination) # Pass the full object
    
@app.route('/admin/order/status/<int:id>', methods=['POST'])
@admin_required
def admin_update_order_status(id):
    order = Order.query.get_or_404(id)
    new_status = request.form['status']
    order.status = new_status
    db.session.commit()
    flash(f"Order #{id} status updated to {new_status}.", "success")
    return redirect(url_for('admin_orders'))

@app.route('/admin/customers')
@admin_required
def admin_customers():
    # Only fetch non-admin users
    users = User.query.filter_by(is_admin=False).all()
    return render_template('admin/customers.html', users=users)


@app.route('/admin/customer/<int:user_id>')
@admin_required
def admin_customer_details(user_id):
    # Fetch the specific user and ensure they are not an admin (optional check)
    customer = User.query.filter_by(id=user_id, is_admin=False).first_or_404()
    
    # Eagerly load all related orders and their payment status for efficiency
    customer_orders = Order.query.options(db.joinedload(Order.payment)).filter_by(user_id=user_id).order_by(Order.created.desc()).all()
    
    # Calculate lifetime value (simple sum of non-pending order totals)
    lifetime_value = db.session.query(func.sum(Order.total)).filter(
        Order.user_id == user_id,
        Order.status.in_(['Shipped', 'Delivered'])
    ).scalar() or 0
    
    return render_template('admin/customer_details.html', 
                           customer=customer, 
                           orders=customer_orders, 
                           lifetime_value=lifetime_value)

# ===== CHATBOT ROUTES =====
# ---------------------------------------------------------
# Chatbot Helper Function (Place this above the /api/chat route)
# ---------------------------------------------------------
def get_chatbot_system_prompt():
    """Generates a system prompt with bulk discount logic."""
    
    # 1. Fetch products
    products = Product.query.all()
    
    # 2. Create menu list
    inventory_text = "CURRENT MENU & BASE PRICING:\n"
    for p in products:
        stock_status = "In Stock" if p.stock > 0 else "Out of Stock"
        # Explicitly state this is the base price
        inventory_text += f"- {p.name}\n  Available Sizes: {p.qty}\n  Base Price: ₹{p.price} (Price for the smallest size listed)\n  Category: {p.category}\n  Status: {stock_status}\n\n"

    # 3. Define the Logic with the Discount Rule
    system_prompt = f"""
    You are 'Amma's Helper', the sales assistant for Amma's Kitchen.
    
    PRICING & DISCOUNT RULES:
    1. The "Base Price" listed applies to the SMALLEST size in "Available Sizes".
    
    2. FOR LARGER SIZES, APPLY A BULK DISCOUNT:
       Step A: Calculate the proportional price (e.g., if 250g is 2.5x the size of 100g, multiply base price by 2.5).
       Step B: **SUBTRACT 10%** from that total as a "Bulk Savings" discount.
       Step C: Round the final number to the nearest whole Rupee.

    EXAMPLE CALCULATION:
    - Product: Sambar Powder. Base: 100g @ ₹60.
    - Customer wants: 1kg (which is 10x the base).
    - Math: 
      1. Normal Price: 60 * 10 = ₹600.
      2. Discount: 10% of 600 is ₹60.
      3. Final Price: 600 - 60 = ₹540.
    
    YOUR BEHAVIOR:
    - If a user asks for a large quantity, explicitly mention the savings. 
      (e.g., "For 1kg, the price is ₹540 (including a 10% discount!)")
    - Be warm and polite.
    - Only sell items listed below.

    {inventory_text}
    """
    return system_prompt

def get_fallback_response(user_message):
    """Backup logic when AI is down or quota exceeded"""
    msg = user_message.lower()
    
    # 1. Simple Keyword Matching
    if 'Sambar cost' in msg or 'sambar cost' in msg  or 'sambar price' in msg:
        return "Our prices start at ₹60 for Sambar Powder. Larger sizes have a discount! Check the menu above."
    elif 'delivery' in msg or 'ship' in msg:
        return "Yes! We deliver fresh to your doorstep. Most orders arrive within 45 minutes."
    elif 'hello' in msg or 'hi' in msg or 'namaste' in msg:
        return "Namaste! 🙏 I am Amma's backup assistant. The main AI is taking a nap, but I can still help!"
    elif 'stock' in msg or 'available' in msg:
        return "Yes, we update our stock daily. Everything listed in the menu is available."
    elif 'contact' in msg or 'phone' in msg:
        return "You can reach us at contact@ammaskitchen.in or call +91-9999999999."
    else:
        # 2. Generic Safe Response
        return "I'm having trouble connecting to my main brain right now. Please check the menu section above for all product details!"
   
@app.route('/api/chat', methods=['POST'])
def chat():
    """Smart Chatbot with Auto-Fallback"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Initialize conversation history if new
        if session_id not in conversations:
            conversations[session_id] = []
        
        # ---------------------------------------------------------
        # PLAN A: TRY GOOGLE GEMINI (The Smart Brain)
        # ---------------------------------------------------------
        try:
            # 1. Prepare Prompt
            system_instruction = get_chatbot_system_prompt()
            full_prompt = system_instruction + "\n\nChat History:\n"
            for msg in conversations[session_id][-10:]: # Keep last 10 msgs
                role = "User" if msg['role'] == 'user' else "Model"
                full_prompt += f"{role}: {msg['content']}\n"
            full_prompt += f"User: {user_message}\nModel:"

            # 2. Call API
            response = model.generate_content(full_prompt)
            assistant_message = response.text
            
            # If successful, save to history
            conversations[session_id].append({'role': 'user', 'content': user_message})
            conversations[session_id].append({'role': 'assistant', 'content': assistant_message})

        # ---------------------------------------------------------
        # PLAN B: FALLBACK TO BACKUP BRAIN (The "Mock" Brain)
        # ---------------------------------------------------------
        except Exception as e:
            print(f"⚠️ Google API Failed: {e}")
            print("🔄 Switching to Fallback Mode...")
            
            # Call our backup function
            assistant_message = get_fallback_response(user_message)
            
            # We don't save fallback messages to history to avoid confusing the AI later
    
        # ---------------------------------------------------------
        # RETURN RESPONSE (Either A or B)
        # ---------------------------------------------------------
        return jsonify({
            'message': assistant_message,
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        # If even the fallback fails (very rare), return a generic error
        print(f"Critical Error: {str(e)}")
        return jsonify({
            'message': "I am currently offline. Please refresh the page.",
            'session_id': session_id
        })     
# ===== END CHATBOT ROUTES =====

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)