from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import re
import secrets
from models import db, User, Product, CartItem, Order, OrderItem, Review
import os
from werkzeug.utils import secure_filename

from datetime import datetime
from werkzeug.utils import secure_filename
import logging



app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///frozen_food.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'rb0494259@gmail.com'
app.config['MAIL_PASSWORD'] = 'rsck tzit gtym ehwx'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'images')
# Configure logging
logging.basicConfig(level=logging.DEBUG)

db.init_app(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
# photos = UploadSet('images', IMAGES)
# configure_uploads(app, photos)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# FR1: User Registration and Login
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        contact = request.form['contact']
        if not re.match(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$', password):
            flash('Password must be at least 8 characters with letters, numbers, and special characters.')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first() or User.query.filter_by(username=username).first():
            flash('Email or username already registered.')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password, contact=contact)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid email or password.')
    return render_template('login.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_hex(16)
            user.reset_token = token
            db.session.commit()
            msg = Message('Password Reset Request', sender=app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f'To reset your password, visit: {url_for("reset_password", token=token, _external=True)}'
            mail.send(msg)
            flash('Password reset link sent to your email.')
        else:
            flash('Email not found.')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user:
        flash('Invalid or expired token.')
        return redirect(url_for('login'))
    if request.method == 'POST':
        password = request.form['password']
        if not re.match(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$', password):
            flash('Password must be at least 8 characters with letters, numbers, and special characters.')
            return redirect(url_for('reset_password', token=token))
        user.password = generate_password_hash(password)
        user.reset_token = None
        db.session.commit()
        flash('Password reset successfully. Please log in.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# FR2: Product Catalog
@app.route('/')
def index():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    query = Product.query
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))
    if category:
        query = query.filter_by(category=category)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    products = query.order_by(Product.created_at.desc()).all()
    categories = db.session.query(Product.category).distinct().all()
    return render_template('index.html', products=products, categories=[c[0] for c in categories])

# FR2: Product Catalog
@app.route('/product/<int:product_id>')
def product(product_id):
    product = Product.query.get_or_404(product_id)
    reviews = Review.query.filter_by(product_id=product_id, is_approved=True).all()
    # Prepare a list of dictionaries with review details including user names
    reviews_with_users = [
        {
            'id': review.id,
            'comment': review.comment,
            'rating': review.rating,
            'user_name': User.query.get(review.user_id).username if User.query.get(review.user_id) else 'Unknown User'
        }
        for review in reviews
    ]
    return render_template('product.html', product=product, reviews=reviews_with_users)

# FR3: Shopping Cart Management
@app.route('/cart')
@login_required
def cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.quantity * item.product.price for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/cart/add/<int:product_id>')
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(user_id=current_user.id, product_id=product_id)
        db.session.add(cart_item)
    db.session.commit()
    flash(f'Added {product.name} to cart!')
    return redirect(url_for('index'))

@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    quantity = int(request.form['quantity'])
    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.user_id == current_user.id and quantity > 0:
        cart_item.quantity = quantity
        db.session.commit()
    return redirect(url_for('cart'))

@app.route('/cart/remove/<int:item_id>')
@login_required
def remove_from_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    if cart_item.user_id == current_user.id:
        db.session.delete(cart_item)
        db.session.commit()
    return redirect(url_for('cart'))



# FR4: Secure Payment Processing
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.quantity * item.product.price for item in cart_items)
    if request.method == 'POST':
        payment_method = request.form['payment_method']
        if not payment_method:
            flash('Please select a payment method.')
            return redirect(url_for('checkout'))
        
        # Create and commit the Order first to get the order_id
        order = Order(user_id=current_user.id, total=total, payment_method=payment_method)
        db.session.add(order)
        db.session.flush()  # Flush to get the order_id without committing the transaction
        
        # Create OrderItem records using the flushed order_id
        for item in cart_items:
            order_item = OrderItem(order_id=order.id, product_id=item.product_id, quantity=item.quantity, price=item.product.price)
            db.session.add(order_item)
        
        # Delete each cart item individually
        for item in cart_items:
            db.session.delete(item)
        
        db.session.commit()  # Commit the transaction
        flash('Order placed successfully!')
        return redirect(url_for('account'))
    return render_template('checkout.html', cart_items=cart_items, total=total)

# FR5: User Account Management
@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    if request.method == 'POST':
        current_user.username = request.form.get('username', current_user.username)
        current_user.email = request.form.get('email', current_user.email)
        current_user.contact = request.form.get('contact', current_user.contact)
        db.session.commit()
        flash('Profile updated successfully!')
    orders = Order.query.filter_by(user_id=current_user.id).all()
    return render_template('account.html', user=current_user, orders=orders)


# FR6: Admin Panel for Product Management
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied.')
        return redirect(url_for('index'))
    products = Product.query.all()
    orders = Order.query.all()
    all_reviews = Review.query.all()  # Fetch all reviews
    logging.debug(f"Number of reviews fetched: {len(all_reviews)}")
    # Prepare a list of dictionaries with review details including product names
    reviews_with_details = [
        {
            'id': review.id,
            'product_name': Product.query.get(review.product_id).name if Product.query.get(review.product_id) else 'Unknown Product',
            'user_name': User.query.get(review.user_id).username if User.query.get(review.user_id) else 'Unknown User',
            'comment': review.comment,
            'rating': review.rating,
            'status': 'approved' if review.is_approved else 'pending'
        }
        for review in all_reviews
    ]
    logging.debug(f"Reviews with details: {reviews_with_details}")
    return render_template('admin/dashboard.html', products=products, orders=orders, reviews=reviews_with_details)


# Add delete review route
@app.route('/admin/review/delete/<int:review_id>')
@login_required
def delete_review(review_id):
    if not current_user.is_admin:
        flash('Access denied.')
        return redirect(url_for('index'))
    review = Review.query.get_or_404(review_id)
    try:
        db.session.delete(review)
        db.session.commit()
        flash('Review deleted successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting review: {str(e)}')
    return redirect(url_for('admin_dashboard'))




@app.route('/admin/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if not current_user.is_admin:
        flash('Access denied.')
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        image = request.files.get('image')
        if image:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        else:
            filename = None
        product = Product(name=name, description=description, price=price, category=category, image=filename)
        db.session.add(product)
        db.session.commit()
        flash('Product added successfully!')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/products.html')

@app.route('/admin/product/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    if not current_user.is_admin:
        flash('Access denied.')
        return redirect(url_for('index'))
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form['description']
        product.price = float(request.form['price'])
        product.category = request.form['category']
        image = request.files.get('image')
        if image:
             filename = secure_filename(image.filename)
             image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
             product.image = filename if image else product.image
        db.session.commit()
        flash('Product updated successfully!')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/products.html', product=product)


# FR6: Admin Panel for Product Management
@app.route('/admin/product/delete/<int:product_id>')
@login_required
def delete_product(product_id):
    if not current_user.is_admin:
        flash('Access denied.')
        return redirect(url_for('index'))
    product = Product.query.get_or_404(product_id)
    try:
        # Delete all OrderItem records associated with the product
        OrderItem.query.filter_by(product_id=product_id).delete()
        # Delete all CartItem records associated with the product
        CartItem.query.filter_by(product_id=product_id).delete()
        # Delete the product
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}')
    return redirect(url_for('admin_dashboard'))





# FR7: Order Management System
@app.route('/admin/order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def manage_order(order_id):
    if not current_user.is_admin:
        flash('Access denied.')
        return redirect(url_for('index'))
    order = Order.query.get_or_404(order_id)
    if request.method == 'POST':
        order.status = request.form['status']
        if order.status == 'delivered':
            msg = Message('Order Delivered', sender=app.config['MAIL_USERNAME'], recipients=[order.user.email])
            msg.body = f'Your order #{order.id} has been delivered on {datetime.utcnow()}.'
            mail.send(msg)
        db.session.commit()
        flash('Order status updated!')
    return render_template('admin/orders.html', order=order)





@app.route('/admin/order/delete/<int:order_id>')
@login_required
def delete_order(order_id):
    if not current_user.is_admin:
        flash('Access denied.')
        return redirect(url_for('index'))
    order = Order.query.get_or_404(order_id)
    try:
        # Delete all OrderItem records associated with the order
        OrderItem.query.filter_by(order_id=order_id).delete()
        # Delete the order
        db.session.delete(order)
        db.session.commit()
        flash('Order deleted successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting order: {str(e)}')
    return redirect(url_for('admin_dashboard'))




# FR8: Customer Comment and Rating System
@app.route('/product/<int:product_id>/review', methods=['GET', 'POST'])
@login_required
def add_review(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        comment = request.form['comment']
        rating = int(request.form['rating'])
        review = Review(product_id=product_id, user_id=current_user.id, comment=comment, rating=rating)
        db.session.add(review)
        db.session.commit()
        flash('Review submitted for approval!')
        return redirect(url_for('product', product_id=product_id))
    return render_template('product.html', product=product, reviews=Review.query.filter_by(product_id=product_id, is_approved=True).all())

@app.route('/admin/review/approve/<int:review_id>')
@login_required
def approve_review(review_id):
    if not current_user.is_admin:
        flash('Access denied.')
        return redirect(url_for('index'))
    review = Review.query.get_or_404(review_id)
    review.is_approved = True
    db.session.commit()
    flash('Review approved!')
    return redirect(url_for('admin_dashboard'))



@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')




if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            admin = User(username='admin', email='admin@example.com', password=generate_password_hash('Admin@123'), contact='1234567890', is_admin=True)
            db.session.add(admin)
            db.session.commit()
        if not Product.query.first():
            sample_products = [
                Product(name="Frozen Pizza", description="Pepperoni pizza", price=10.99, category="frozen meals", image="pizza.jpg"),
                Product(name="Homemade Lasagna", description="Beef lasagna", price=12.99, category="cooked dishes", image="lasagna.jpg"),
            ]
            db.session.add_all(sample_products)
            db.session.commit()
    app.run(debug=True) 