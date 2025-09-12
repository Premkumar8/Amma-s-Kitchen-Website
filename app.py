from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# -------------------------------
# Database Config
# -------------------------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://username:password@localhost/db_name'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------------------
# Models
# -------------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(200), nullable=False)
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
    created = db.Column(db.DateTime, default=datetime.utcnow)
    images = db.relationship("ProductImage", backref="product", lazy=True)

class ProductImage(db.Model):
    __tablename__ = "product_images"
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(255), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

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
    product = db.relationship("Product", backref="orders", lazy=True)
    payment = db.relationship("Payment", backref="order", uselist=False)

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
# Auth Routes
# -------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash("Logged in successfully!", "success")
            return redirect(url_for('index'))
        flash("Invalid credentials", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for('login'))

# -------------------------------
# Index
# -------------------------------
@app.route('/')
def index():
    return render_template('index.html')

# -------------------------------
# User CRUD
# -------------------------------
@app.route('/users')
def users_list():
    users = User.query.all()
    return render_template('users/list.html', users=users)

@app.route('/users/add', methods=['GET', 'POST'])
def user_add():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = generate_password_hash(request.form['password'])
        user = User(name=name, email=email, phone=phone, password=password)
        db.session.add(user)
        db.session.commit()
        flash("User added successfully", "success")
        return redirect(url_for('users_list'))
    return render_template('users/add.html')

@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
def user_edit(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        user.name = request.form['name']
        user.email = request.form['email']
        user.phone = request.form['phone']
        if request.form['password']:
            user.password = generate_password_hash(request.form['password'])
        db.session.commit()
        flash("User updated successfully", "success")
        return redirect(url_for('users_list'))
    return render_template('users/edit.html', user=user)

@app.route('/users/delete/<int:id>')
def user_delete(id):
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully", "success")
    return redirect(url_for('users_list'))

# -------------------------------
# Product CRUD
# -------------------------------
@app.route('/products')
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
# Orders, Payment, Banner CRUD
# Similar routes can be created like Users & Products
# -------------------------------
# -------------------------------
# Orders CRUD
# -------------------------------
@app.route('/orders')
def orders_list():
    orders = Order.query.all()
    return render_template('orders/list.html', orders=orders)

@app.route('/orders/add', methods=['GET', 'POST'])
def order_add():
    users = User.query.all()
    products = Product.query.all()
    if request.method == 'POST':
        user_id = request.form['user_id']
        product_id = request.form['product_id']
        total = request.form['total']
        address = request.form['address']
        note = request.form['note']
        status = request.form.get('status', 'Pending')
        order = Order(user_id=user_id, product_id=product_id, total=total, address=address, note=note, status=status)
        db.session.add(order)
        db.session.commit()
        flash("Order added successfully", "success")
        return redirect(url_for('orders_list'))
    return render_template('orders/add.html', users=users, products=products)

@app.route('/orders/edit/<int:id>', methods=['GET', 'POST'])
def order_edit(id):
    order = Order.query.get_or_404(id)
    users = User.query.all()
    products = Product.query.all()
    if request.method == 'POST':
        order.user_id = request.form['user_id']
        order.product_id = request.form['product_id']
        order.total = request.form['total']
        order.address = request.form['address']
        order.note = request.form['note']
        order.status = request.form.get('status', order.status)
        db.session.commit()
        flash("Order updated successfully", "success")
        return redirect(url_for('orders_list'))
    return render_template('orders/edit.html', order=order, users=users, products=products)

@app.route('/orders/delete/<int:id>')
def order_delete(id):
    order = Order.query.get_or_404(id)
    db.session.delete(order)
    db.session.commit()
    flash("Order deleted successfully", "success")
    return redirect(url_for('orders_list'))

# -------------------------------
# Payments CRUD
# -------------------------------
@app.route('/payments')
def payments_list():
    payments = Payment.query.all()
    return render_template('payments/list.html', payments=payments)

@app.route('/payments/add', methods=['GET', 'POST'])
def payment_add():
    orders = Order.query.all()
    if request.method == 'POST':
        order_id = request.form['order_id']
        status = request.form.get('status', 'Unpaid')
        payment = Payment(order_id=order_id, status=status)
        db.session.add(payment)
        db.session.commit()
        flash("Payment added successfully", "success")
        return redirect(url_for('payments_list'))
    return render_template('payments/add.html', orders=orders)

@app.route('/payments/edit/<int:id>', methods=['GET', 'POST'])
def payment_edit(id):
    payment = Payment.query.get_or_404(id)
    orders = Order.query.all()
    if request.method == 'POST':
        payment.order_id = request.form['order_id']
        payment.status = request.form.get('status', payment.status)
        db.session.commit()
        flash("Payment updated successfully", "success")
        return redirect(url_for('payments_list'))
    return render_template('payments/edit.html', payment=payment, orders=orders)

@app.route('/payments/delete/<int:id>')
def payment_delete(id):
    payment = Payment.query.get_or_404(id)
    db.session.delete(payment)
    db.session.commit()
    flash("Payment deleted successfully", "success")
    return redirect(url_for('payments_list'))

# -------------------------------
# Banners CRUD
# -------------------------------
@app.route('/banners')
def banners_list():
    banners = Banner.query.all()
    return render_template('banners/list.html', banners=banners)

@app.route('/banners/add', methods=['GET', 'POST'])
def banner_add():
    if request.method == 'POST':
        name = request.form['name']
        image = request.form['image']  # You can integrate file upload here
        banner = Banner(name=name, image=image)
        db.session.add(banner)
        db.session.commit()
        flash("Banner added successfully", "success")
        return redirect(url_for('banners_list'))
    return render_template('banners/add.html')

@app.route('/banners/edit/<int:id>', methods=['GET', 'POST'])
def banner_edit(id):
    banner = Banner.query.get_or_404(id)
    if request.method == 'POST':
        banner.name = request.form['name']
        banner.image = request.form['image']
        db.session.commit()
        flash("Banner updated successfully", "success")
        return redirect(url_for('banners_list'))
    return render_template('banners/edit.html', banner=banner)

@app.route('/banners/delete/<int:id>')
def banner_delete(id):
    banner = Banner.query.get_or_404(id)
    db.session.delete(banner)
    db.session.commit()
    flash("Banner deleted successfully", "success")
    return redirect(url_for('banners_list'))

# -------------------------------
# Product Detail Page & User Orders
# -------------------------------
@app.route('/product/<int:product_id>', methods=['GET', 'POST'])
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Get images
    images = ProductImage.query.filter_by(product_id=product.id).all()
    
    # Fetch orders for logged-in user
    orders = []
    if 'user_id' in session:
        orders = Order.query.filter_by(user_id=session['user_id']).all()

    return render_template('orders/orders.html', product=product, images=images, orders=orders)


# -------------------------------
# Add to Cart / Place Order
# -------------------------------
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash("Please login to place an order", "danger")
        return redirect(url_for('login'))

    product = Product.query.get_or_404(product_id)
    quantity = int(request.form.get('quantity', 1))
    
    if quantity > product.stock:
        flash('Not enough stock available!', 'danger')
        return redirect(url_for('product_detail', product_id=product.id))

    total_price = quantity * product.price

    # Create order
    new_order = Order(
        user_id=session['user_id'],
        product_id=product.id,
        total=total_price,
        address=request.form.get('address', ''),
        note=request.form.get('note', ''),
        status='Pending'
    )
    db.session.add(new_order)

    # Reduce stock
    product.stock -= quantity
    db.session.commit()

    flash(f'Added {quantity} x {product.name} to your orders!', 'success')
    return redirect(url_for('product_detail', product_id=product.id))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)