# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///spare_parts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'admin', 'seller', 'buyer'
    
    # Relationships
    seller_info = db.relationship('SellerInfo', backref='user', uselist=False)
    products = db.relationship('Product', backref='seller', lazy=True)
    orders = db.relationship('Order', backref='buyer', lazy=True)
    cart_items = db.relationship('CartItem', backref='user', lazy=True)

class SellerInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shop_name = db.Column(db.String(100), nullable=False)
    shop_address = db.Column(db.String(255), nullable=False)
    gstin = db.Column(db.String(20), nullable=False)
    pan_number = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 'bike', 'car', 'both'
    is_approved = db.Column(db.Boolean, default=False)
    
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 'bike', 'car'
    image = db.Column(db.String(255), nullable=True)
    eta = db.Column(db.Integer, nullable=False)  # Estimated time of arrival in days
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    cart_items = db.relationship('CartItem', backref='product', lazy=True)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'shipped', 'delivered'
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy=True)
    
class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)  # Price at the time of purchase

class Query(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')  # 'open', 'in_progress', 'resolved'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
# Create database and initial admin
with app.app_context():
    db.create_all()
    
    # Check if admin exists, if not create one
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(
            phone="admin",
            password=generate_password_hash("1234567"),
            name="Admin",
            email="admin@spareparts.com",
            address="Admin Office",
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created!")

# Decorators for role-based access control
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('You need admin privileges to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def seller_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'seller':
            flash('You need seller privileges to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def approved_seller_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'seller':
            flash('You need seller privileges to access this page.', 'danger')
            return redirect(url_for('index'))
        
        seller_info = SellerInfo.query.filter_by(user_id=session['user_id']).first()
        if not seller_info or not seller_info.is_approved:
            flash('Your seller account is pending approval.', 'warning')
            return redirect(url_for('profile'))
            
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    products = Product.query.join(SellerInfo, Product.seller_id == SellerInfo.user_id).filter(SellerInfo.is_approved == True).all()
    return render_template('index.html', products=products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        user = User.query.filter_by(phone=phone).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['name'] = user.name
            session['role'] = user.role
            
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Invalid phone number or password', 'danger')
    
    return render_template('login.html')

@app.route('/check_phone', methods=['POST'])
def check_phone():
    phone = request.form.get('phone')
    user = User.query.filter_by(phone=phone).first()
    
    if user:
        return {'exists': True}
    else:
        return {'exists': False}

@app.route('/register/buyer', methods=['GET', 'POST'])
def register_buyer():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        address = request.form.get('address')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        user = User.query.filter_by(phone=phone).first()
        if user:
            flash('Phone number already registered. Please login.', 'warning')
            return redirect(url_for('login'))
        
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('register_buyer.html')
        
        new_user = User(
            name=name,
            phone=phone,
            email=email,
            address=address,
            password=generate_password_hash(password),
            role='buyer'
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register_buyer.html')

@app.route('/register/seller', methods=['GET', 'POST'])
def register_seller():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        address = request.form.get('address')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        shop_name = request.form.get('shop_name')
        shop_address = request.form.get('shop_address')
        gstin = request.form.get('gstin')
        pan_number = request.form.get('pan_number')
        category = request.form.get('category')
        
        user = User.query.filter_by(phone=phone).first()
        if user:
            flash('Phone number already registered. Please login.', 'warning')
            return redirect(url_for('login'))
        
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('register_seller.html')
        
        new_user = User(
            name=name,
            phone=phone,
            email=email,
            address=address,
            password=generate_password_hash(password),
            role='seller'
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        seller_info = SellerInfo(
            user_id=new_user.id,
            shop_name=shop_name,
            shop_address=shop_address,
            gstin=gstin,
            pan_number=pan_number,
            category=category
        )
        
        db.session.add(seller_info)
        db.session.commit()
        
        flash('Seller registration successful! Your account is pending approval.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register_seller.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    user = User.query.get(session['user_id'])
    
    if user.role == 'seller':
        seller_info = SellerInfo.query.filter_by(user_id=user.id).first()
        products = Product.query.filter_by(seller_id=user.id).all()
        return render_template('seller_profile.html', user=user, seller_info=seller_info, products=products)
    
    elif user.role == 'buyer':
        cart_items = CartItem.query.filter_by(user_id=user.id).all()
        orders = Order.query.filter_by(user_id=user.id).all()
        products = Product.query.join(SellerInfo, Product.seller_id == SellerInfo.user_id).filter(SellerInfo.is_approved == True).all()
        return render_template('buyer_profile.html', user=user, cart_items=cart_items, orders=orders, products=products)
    
    elif user.role == 'admin':
        pending_sellers = SellerInfo.query.filter_by(is_approved=False).all()
        all_users = User.query.filter(User.role != 'admin').all()
        queries = Query.query.all()
        return render_template('admin_profile.html', user=user, pending_sellers=pending_sellers, all_users=all_users, queries=queries)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        user.name = request.form.get('name')
        user.email = request.form.get('email')
        user.address = request.form.get('address')
        
        if user.role == 'seller':
            seller_info = SellerInfo.query.filter_by(user_id=user.id).first()
            seller_info.shop_name = request.form.get('shop_name')
            seller_info.shop_address = request.form.get('shop_address')
            seller_info.category = request.form.get('category')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    if user.role == 'seller':
        seller_info = SellerInfo.query.filter_by(user_id=user.id).first()
        return render_template('edit_seller_profile.html', user=user, seller_info=seller_info)
    else:
        return render_template('edit_buyer_profile.html', user=user)

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        user = User.query.get(session['user_id'])
        
        if not check_password_hash(user.password, current_password):
            flash('Current password is incorrect!', 'danger')
            return redirect(url_for('change_password'))
            
        if new_password != confirm_password:
            flash('New passwords do not match!', 'danger')
            return redirect(url_for('change_password'))
            
        user.password = generate_password_hash(new_password)
        db.session.commit()
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('profile'))
        
    return render_template('change_password.html')

@app.route('/add_product', methods=['GET', 'POST'])
@approved_seller_required
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        stock = int(request.form.get('stock'))
        category = request.form.get('category')
        eta = int(request.form.get('eta'))
        
        image = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                image = 'uploads/' + filename
        
        new_product = Product(
            seller_id=session['user_id'],
            name=name,
            description=description,
            price=price,
            stock=stock,
            category=category,
            image=image,
            eta=eta
        )
        
        db.session.add(new_product)
        db.session.commit()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('profile'))
        
    return render_template('add_product.html')

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@seller_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Check if the seller owns this product
    if product.seller_id != session['user_id']:
        flash('You do not have permission to edit this product.', 'danger')
        return redirect(url_for('profile'))
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.stock = int(request.form.get('stock'))
        product.category = request.form.get('category')
        product.eta = int(request.form.get('eta'))
        
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                product.image = 'uploads/' + filename
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('profile'))
        
    return render_template('edit_product.html', product=product)

@app.route('/delete_product/<int:product_id>')
@seller_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if product.seller_id != session['user_id']:
        flash('You do not have permission to delete this product.', 'danger')
        return redirect(url_for('profile'))
        
    db.session.delete(product)
    db.session.commit()
    
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('profile'))

@app.route('/search')
def search():
    query = request.args.get('query', '')
    category = request.args.get('category', '')
    
    products = Product.query.join(SellerInfo, Product.seller_id == SellerInfo.user_id).filter(SellerInfo.is_approved == True)
    
    if query:
        products = products.filter(Product.name.contains(query) | Product.description.contains(query))
    
    if category:
        products = products.filter(Product.category == category)
        
    products = products.all()
    
    return render_template('search_results.html', products=products, query=query, selected_category=category)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    seller = User.query.get(product.seller_id)
    return render_template('product_detail.html', product=product, seller=seller)

@app.route('/add_to_cart/<int:product_id>')
@login_required
def add_to_cart(product_id):
    if session.get('role') != 'buyer':
        flash('Only buyers can add items to cart!', 'warning')
        return redirect(url_for('product_detail', product_id=product_id))
    
    product = Product.query.get_or_404(product_id)
    
    # Check if product is already in cart
    cart_item = CartItem.query.filter_by(user_id=session['user_id'], product_id=product_id).first()
    
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(user_id=session['user_id'], product_id=product_id, quantity=1)
        db.session.add(cart_item)
    
    db.session.commit()
    flash('Product added to cart!', 'success')
    return redirect(url_for('view_cart'))

@app.route('/view_cart')
@login_required
def view_cart():
    if session.get('role') != 'buyer':
        flash('Only buyers can view cart!', 'warning')
        return redirect(url_for('index'))
    
    cart_items = CartItem.query.filter_by(user_id=session['user_id']).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/update_cart/<int:cart_id>', methods=['POST'])
@login_required
def update_cart(cart_id):
    cart_item = CartItem.query.get_or_404(cart_id)
    
    if cart_item.user_id != session['user_id']:
        flash('You do not have permission to modify this cart item.', 'danger')
        return redirect(url_for('view_cart'))
    
    quantity = int(request.form.get('quantity'))
    
    if quantity <= 0:
        db.session.delete(cart_item)
    else:
        cart_item.quantity = quantity
    
    db.session.commit()
    flash('Cart updated!', 'success')
    return redirect(url_for('view_cart'))

@app.route('/remove_from_cart/<int:cart_id>')
@login_required
def remove_from_cart(cart_id):
    cart_item = CartItem.query.get_or_404(cart_id)
    
    if cart_item.user_id != session['user_id']:
        flash('You do not have permission to remove this cart item.', 'danger')
        return redirect(url_for('view_cart'))
    
    db.session.delete(cart_item)
    db.session.commit()
    
    flash('Item removed from cart!', 'success')
    return redirect(url_for('view_cart'))

@app.route('/checkout')
@login_required
def checkout():
    if session.get('role') != 'buyer':
        flash('Only buyers can checkout!', 'warning')
        return redirect(url_for('index'))
    
    cart_items = CartItem.query.filter_by(user_id=session['user_id']).all()
    
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('view_cart'))
    
    # Create order
    new_order = Order(user_id=session['user_id'])
    db.session.add(new_order)
    db.session.commit()
    
    # Create order items
    for cart_item in cart_items:
        product = cart_item.product
        
        # Check stock
        if product.stock < cart_item.quantity:
            flash(f'Not enough stock for {product.name}!', 'danger')
            db.session.delete(new_order)
            db.session.commit()
            return redirect(url_for('view_cart'))
        
        # Update stock
        product.stock -= cart_item.quantity
        
        # Create order item
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=product.id,
            quantity=cart_item.quantity,
            price=product.price
        )
        db.session.add(order_item)
        
        # Remove cart item
        db.session.delete(cart_item)
    
    db.session.commit()
    flash('Order placed successfully!', 'success')
    return redirect(url_for('view_orders'))

@app.route('/view_orders')
@login_required
def view_orders():
    if session.get('role') != 'buyer':
        flash('Only buyers can view orders!', 'warning')
        return redirect(url_for('index'))
    
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.order_date.desc()).all()
    
    # Pre-calculate totals for each order
    orders_with_totals = []
    for order in orders:
        total = sum(item.price * item.quantity for item in order.items)
        orders_with_totals.append({
            'order': order,
            'total': total
        })
    
    return render_template('orders.html', orders_with_totals=orders_with_totals)

@app.route('/view_order/<int:order_id>')
@login_required
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != session['user_id'] and session.get('role') != 'admin':
        flash('You do not have permission to view this order.', 'danger')
        return redirect(url_for('view_orders'))
    total = sum(item.price * item.quantity for item in order.items)
    return render_template('order_detail.html', order=order, total=total)
@app.route('/admin/approve_seller/<int:seller_info_id>')
@admin_required
def approve_seller(seller_info_id):
    seller_info = SellerInfo.query.get_or_404(seller_info_id)
    seller_info.is_approved = True
    db.session.commit()
    
    flash('Seller approved!', 'success')
    return redirect(url_for('profile'))

@app.route('/admin/reject_seller/<int:seller_info_id>')
@admin_required
def reject_seller(seller_info_id):
    seller_info = SellerInfo.query.get_or_404(seller_info_id)
    user = User.query.get(seller_info.user_id)
    
    db.session.delete(seller_info)
    db.session.delete(user)
    db.session.commit()
    
    flash('Seller rejected and account removed!', 'success')
    return redirect(url_for('profile'))

@app.route('/admin/view_user/<int:user_id>')
@admin_required
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.role == 'seller':
        seller_info = SellerInfo.query.filter_by(user_id=user.id).first()
        products = Product.query.filter_by(seller_id=user.id).all()
        return render_template('admin_view_seller.html', user=user, seller_info=seller_info, products=products)
    else:
        orders = Order.query.filter_by(user_id=user.id).all()
        return render_template('admin_view_buyer.html', user=user, orders=orders)

@app.route('/submit_query', methods=['GET', 'POST'])
@login_required
def submit_query():
    if request.method == 'POST':
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        new_query = Query(
            user_id=session['user_id'],
            subject=subject,
            message=message
        )
        
        db.session.add(new_query)
        db.session.commit()
        
        flash('Query submitted successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('submit_query.html')

@app.route('/admin/update_query/<int:query_id>', methods=['POST'])
@admin_required
def update_query(query_id):
    query = Query.query.get_or_404(query_id)
    status = request.form.get('status')
    
    query.status = status
    db.session.commit()
    
    flash('Query status updated!', 'success')
    return redirect(url_for('profile'))
@app.route('/view_buyer/<int:user_id>')
@login_required
def view_buyer(user_id):
    if session.get('role') != 'admin':
        flash('Only admins can view buyer details!', 'danger')
        return redirect(url_for('index'))
    
    buyer = User.query.get_or_404(user_id)
    if buyer.role != 'buyer':
        flash('This user is not a buyer!', 'warning')
        return redirect(url_for('admin_profile'))
    
    return render_template('admin_view_buyer.html', buyer=buyer)
if __name__ == '__main__':
    app.run(debug=True)