from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from limits.storage import MemoryStorage
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail, Message
import secrets
from datetime import datetime, timedelta
import requests
from urllib.parse import quote
from os import environ

# Load environment variables’ך
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'static/images')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 5 * 1024 * 1024))
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
app.config['GOOGLE_MAPS_API_KEY'] = os.getenv('GOOGLE_MAPS_API_KEY')

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize SQLAlchemy
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://"
)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

app.config['WTF_CSRF_ENABLED'] = False  # Only for debugging!

# Initialize Flask-Mail
mail = Mail()
mail.init_app(app)

# Add this after setting up mail configuration
app.logger.info(f"Mail Configuration:")
app.logger.info(f"MAIL_SERVER: {app.config['MAIL_SERVER']}")
app.logger.info(f"MAIL_PORT: {app.config['MAIL_PORT']}")
app.logger.info(f"MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
app.logger.info(f"MAIL_DEFAULT_SENDER: {app.config['MAIL_DEFAULT_SENDER']}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def handle_image_upload(file, old_image=None):
    try:
        if not file:
            return None, None
            
        if not allowed_file(file.filename):
            return None, "קובץ לא חוקי. יש להעלות תמונות מסוג PNG, JPG, JPEG, או GIF בלבד"
            
        try:
            file.seek(0, os.SEEK_END)
            size = file.tell()
        finally:
            file.seek(0)
        
        if size > app.config['MAX_CONTENT_LENGTH']:
            return None, "גודל הקובץ חורג מ-5MB המותרים"

        # Create images directory if it doesn't exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        # Remove old image if exists
        if old_image:
            try:
                old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], old_image)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            except Exception as e:
                logger.error(f"Error removing old image: {e}")

        # Generate unique filename
        filename = secure_filename(file.filename)
        base, ext = os.path.splitext(filename)
        filename = f"{base}_{uuid.uuid4().hex[:8]}{ext}"

        # Save new image
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        return filename, None
        
    except Exception as e:
        logger.error(f"Error handling image upload: {e}")
        return None, "שגיאה בהעלאת התמונה. אנא נסה שנית"

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    capacity = db.Column(db.Integer)
    image_url = db.Column(db.String(200))

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)

# Add this with your other models
class Newsletter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

# Load events with filtering
def load_events(filters=None):
    try:
        with open('data/events.json', 'r', encoding='utf-8') as file:
            events = json.load(file)
            if not filters:
                return events
            
            filtered_events = events
            if 'city' in filters and filters['city']:
                filtered_events = [e for e in filtered_events 
                                 if filters['city'].lower() in e['location'].lower()]
            if 'date' in filters and filters['date']:
                filtered_events = [e for e in filtered_events 
                                 if e['date'] >= filters['date']]
            if 'type' in filters and filters['type']:
                filtered_events = [e for e in filtered_events 
                                 if filters['type'] in e['type']]
            return filtered_events
    except Exception as e:
        logger.error(f"Error loading events: {e}")
        return []

@app.route('/')
def index():
    app.logger.debug('Accessing index route')
    try:
        return render_template('index.html')
    except Exception as e:
        app.logger.error(f'Error rendering index: {str(e)}')
        return str(e), 500

@app.route('/search')
@limiter.limit("200 per hour")
def search():
    filters = {
        'city': request.args.get('city', ''),
        'date': request.args.get('date', ''),
        'type': request.args.get('type', '')
    }
    events = load_events(filters)
    return render_template('results.html', events=events)

@app.route('/api/favorite/<event_id>', methods=['POST'])
@login_required
def toggle_favorite(event_id):
    favorites = current_user.get_favorites()
    if event_id in favorites:
        favorites.remove(event_id)
    else:
        favorites.append(event_id)
    current_user.favorite_events = json.dumps(favorites)
    db.session.commit()
    return jsonify({'status': 'success', 'favorites': favorites})

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('התחברת בהצלחה!', 'success')
            return redirect(url_for('index'))
        
        flash('אימייל או סיסמה לא נכונים', 'error')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if User.query.filter_by(email=email).first():
            flash('כתובת האימייל כבר קיימת במערכת')
            return redirect(url_for('signup'))
        
        if password != confirm_password:
            flash('הסיסמאות אינן תואמות')
            return redirect(url_for('signup'))
        
        new_user = User(
            email=email,
            password=generate_password_hash(password)
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('נרשמת בהצלחה! אנא התחבר')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/manage')
@login_required
def manage_events():
    if not current_user.is_admin:
        flash('אין לך הרשאות לצפות בדף זה', 'error')
        return redirect(url_for('index'))
    
    with open('data/events.json', 'r', encoding='utf-8') as file:
        events = json.load(file)
    return render_template('manage_events.html', events=events)

@app.route('/event/add', methods=['GET', 'POST'])
@login_required
def add_event():
    if request.method == 'POST':
        event = {
            'id': str(uuid.uuid4()),
            'user_id': current_user.id,
            'title': request.form.get('title'),
            'date': request.form.get('date'),
            'time': request.form.get('time'),
            'location': request.form.get('location'),
            'address': request.form.get('address'),
            'speaker': request.form.get('speaker'),
            'description': request.form.get('description'),
            'capacity': int(request.form.get('capacity')),
            'type': request.form.get('type'),
            'approved': current_user.is_admin,  # Auto-approve for admins
            'created_at': datetime.now().isoformat()
        }
        
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                event['image'] = filename
        
        with open('data/events.json', 'r+', encoding='utf-8') as file:
            events = json.load(file)
            events.append(event)
            file.seek(0)
            json.dump(events, file, ensure_ascii=False, indent=4)
            file.truncate()
        
        flash('ההתוועדות נוצרה בהצלחה' + (' ומחכה לאישור מנהל' if not current_user.is_admin else ''), 'success')
        return redirect(url_for('my_events'))
    
    return render_template('event_form.html', event=None)

@app.route('/event/edit/<event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    try:
        # Load existing events
        with open('data/events.json', 'r', encoding='utf-8') as file:
            events = json.load(file)
        
        event = next((e for e in events if e['id'] == event_id), None)
        
        if not event:
            flash('ההתוועדות לא נמצאה', 'error')
            return redirect(url_for('my_events'))
        
        if current_user.is_admin:
            pass
        elif event.get('user_id') != current_user.id:
            flash('אין לך הרשאה לערוך התוועדות זו', 'error')
            return redirect(url_for('my_events'))

        if request.method == 'POST':
            # Handle image removal
            remove_image = request.form.get('remove_image') == 'true'
            if remove_image and event.get('image'):
                try:
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], event['image'])
                    if os.path.exists(image_path):
                        os.remove(image_path)
                    event['image'] = None
                except Exception as e:
                    flash(f'שגיאה בחיקת התמונה: {str(e)}', 'error')
            
            # Handle new image upload
            if not remove_image and 'image' in request.files:
                file = request.files['image']
                if file.filename:
                    filename, error = handle_image_upload(file, event.get('image'))
                    if error:
                        flash(error, 'error')
                    elif filename:
                        event['image'] = filename

            # Update other event details
            event.update({
                'title': request.form.get('title'),
                'date': request.form.get('date'),
                'time': request.form.get('time'),
                'location': request.form.get('location'),
                'address': request.form.get('address'),
                'speaker': request.form.get('speaker'),
                'description': request.form.get('description'),
                'type': request.form.get('type'),
                'user_id': event.get('user_id', current_user.id),
            })

            # Save updated events
            with open('data/events.json', 'w', encoding='utf-8') as file:
                json.dump(events, file, ensure_ascii=False, indent=4)

            flash('ההתוועדות עודכנה בהצלחה', 'success')
            return redirect(url_for('my_events'))

        return render_template('event_form.html', event=event)
        
    except Exception as e:
        flash(f'שגיאה בעריכת התוועדות: {str(e)}', 'error')
        return redirect(url_for('my_events'))

@app.route('/api/events/<event_id>', methods=['DELETE'])
@login_required
def delete_user_event(event_id):
    with open('data/events.json', 'r', encoding='utf-8') as file:
        events = json.load(file)
    
    event = next((e for e in events if e['id'] == event_id), None)
    if not event:
        return jsonify({'status': 'error', 'message': 'התוועדות לא נמצאה'})
    
    if event['user_id'] != current_user.id and not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'אין לך הרשאות למחוק התוועדות זו'})
    
    events = [e for e in events if e['id'] != event_id]
    
    with open('data/events.json', 'w', encoding='utf-8') as file:
        json.dump(events, file, ensure_ascii=False, indent=4)
    
    return jsonify({'status': 'success'})

@app.route('/manage/users')
@login_required
def manage_users():
    if not current_user.is_admin:
        flash('אין לך הרשאות לצפות בדף זה', 'error')
        return redirect(url_for('index'))
    
    users = User.query.all()
    return render_template('manage_users.html', users=users)

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'אין לך הרשאות למחוק משתמשים'})
    
    if current_user.id == user_id:
        return jsonify({'status': 'error', 'message': 'לא ניתן מחוק את המשתמש הנוכחי'})
    
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'status': 'success'})

@app.route('/api/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
def toggle_admin(user_id):
    if not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'אין לך הרשאות לשנות הרשאות משתמשים'})
    
    if current_user.id == user_id:
        return jsonify({'status': 'error', 'message': 'לא ניתן לשנות הרשאות למשתמש הנוכחי'})
    
    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin
    db.session.commit()
    
    return jsonify({'status': 'success'})

@app.route('/debug_users')
def debug_users():
    users = User.query.all()
    output = []
    for user in users:
        output.append({
            'email': user.email,
            'is_admin': user.is_admin,
            'created_at': str(user.created_at)
        })
    return jsonify(output)

# Add a debug route to check database status
@app.route('/debug_db')
def debug_db():
    try:
        # Check if users table exists
        users = User.query.all()
        user_count = len(users)
        
        # Get details of all users
        user_details = []
        for user in users:
            user_details.append({
                'id': user.id,
                'email': user.email,
                'is_admin': user.is_admin,
                'created_at': str(user.created_at)
            })
        
        return jsonify({
            'database_status': 'connected',
            'user_count': user_count,
            'users': user_details
        })
    except Exception as e:
        return jsonify({
            'database_status': 'error',
            'error': str(e)
        })

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('אין לך הרשאות לצפות בדף זה', 'error')
        return redirect(url_for('index'))
    
    # Load events
    with open('data/events.json', 'r', encoding='utf-8') as file:
        events = json.load(file)
    
    # Get statistics
    current_month = datetime.now().month
    users = User.query.all()
    
    stats = {
        'events_count': len(events),
        'users_count': len(users),
        'admin_count': len([u for u in users if u.is_admin]),
        'monthly_events': len([e for e in events if datetime.strptime(e['date'], '%Y-%m-%d').month == current_month]),
        'new_users': len([u for u in users if u.created_at.month == current_month])
    }
    
    return render_template('admin_dashboard.html', **stats)

@app.route('/api/clear-cache', methods=['POST'])
@login_required
def clear_cache():
    if not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'אין לך הרשאות'})
    
    try:
        # Add cache clearing logic here if needed
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/my-events')
@login_required
def my_events():
    events = load_user_events(current_user.id)
    return render_template('my_events.html', events=events)

def load_user_events(user_id):
    with open('data/events.json', 'r', encoding='utf-8') as file:
        events = json.load(file)
        return [event for event in events if event.get('user_id') == user_id]

@app.route('/logo')
def logo():
    return render_template('logo.html')

@app.route('/subscribe', methods=['POST'])
def subscribe_newsletter():
    email = request.form.get('email')
    
    if not email:
        return jsonify({'status': 'error', 'message': 'נרשת כתובת אימייל'})
    
    try:
        # Check if already subscribed
        existing = Newsletter.query.filter_by(email=email).first()
        if existing:
            if existing.is_active:
                return jsonify({'status': 'error', 'message': 'כתובת האימייל כבר רשומה לניוזלטר'})
            else:
                existing.is_active = True
                db.session.commit()
                return jsonify({'status': 'success', 'message': 'הרשמתך לניוזלטר חודשה בהצלחה'})
        
        # Add new subscriber
        subscriber = Newsletter(email=email)
        db.session.add(subscriber)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'נרשמת בהצלחה לניוזלטר'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Newsletter subscription error: {e}")
        return jsonify({'status': 'error', 'message': 'אירעה שגיאה בהרשמה לניוזלטר'})

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate token and set expiry
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            
            # Create reset link
            reset_link = url_for('reset_password_confirm', token=token, _external=True)
            
            try:
                msg = Message('איפוס סיסמה - ומלאה הארץ פאר��ריינגענס',
                            recipients=[email])
                msg.html = render_template('email/reset_password.html', 
                                        reset_link=reset_link)
                mail.send(msg)
                flash('נשלח אליך מייל עם הוראות לאיפוס הסיסמה', 'info')
            except Exception as e:
                app.logger.error(f"Failed to send email: {str(e)}")
                db.session.rollback()
                flash('אירעה שגיאה בשליחת המייל. אנא נסה שוב מאוחר יותר', 'error')
                return redirect(url_for('reset_password'))
                
        else:
            # For security, show the same message even if email doesn't exist
            flash('נשלח אליך מייל עם הוראות לאיפוס הסיסמה', 'info')
            
        return redirect(url_for('login'))
    
    return render_template('reset_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_confirm(token):
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or not user.reset_token_expiry or \
       user.reset_token_expiry < datetime.utcnow():
        flash('הקישור לאיפוס הסיסמה אינו תקי או פג תוקף', 'error')
        return redirect(url_for('reset_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('הסיסמאות אינן תואמות', 'error')
            return redirect(url_for('reset_password_confirm', token=token))
        
        user.password = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        
        flash('הסיסמה שונתה בהצלחה! אנא התחבר', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password_confirm.html')

@app.route('/test-mail')
def test_mail():
    try:
        app.logger.info("Attempting to send test email...")
        msg = Message('Test Email',
                     recipients=['motiwolff@gmail.com'])
        msg.body = 'This is a test email.'
        mail.send(msg)
        app.logger.info("Email sent successfully!")
        return 'Mail sent successfully!'
    except Exception as e:
        app.logger.error(f"Failed to send email: {str(e)}")
        return f'Error sending mail: {str(e)}'

@app.route('/api/find-liquor-stores')
def find_liquor_stores():
    address = request.args.get('address')
    app.logger.debug(f"Searching for liquor stores near address: {address}")

    if not address:
        return jsonify({'error': 'Address is required'}), 400

    try:
        # First, geocode the address to get coordinates
        geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote(address)}&key={app.config['GOOGLE_MAPS_API_KEY']}"
        app.logger.debug(f"Geocoding URL: {geocode_url}")
        
        geocode_response = requests.get(geocode_url)
        geocode_data = geocode_response.json()
        app.logger.debug(f"Geocoding response: {geocode_data}")

        if geocode_data['status'] != 'OK':
            return jsonify({
                'error': 'Could not find location',
                'google_error': geocode_data['status']
            }), 400

        location = geocode_data['results'][0]['geometry']['location']
        app.logger.debug(f"Found coordinates: {location}")
        
        # Then, search for nearby liquor stores
        places_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={location['lat']},{location['lng']}&radius=1500&type=liquor_store&key={app.config['GOOGLE_MAPS_API_KEY']}"
        app.logger.debug(f"Places search URL: {places_url}")
        
        places_response = requests.get(places_url)
        places_data = places_response.json()
        app.logger.debug(f"Places response: {places_data}")

        if places_data['status'] != 'OK':
            return jsonify({
                'error': 'No liquor stores found',
                'google_error': places_data['status']
            }), 404

        # Format the response
        stores = [{
            'name': place['name'],
            'address': place.get('vicinity', ''),
            'rating': place.get('rating', 'N/A'),
            'open_now': place.get('opening_hours', {}).get('open_now', None),
            'location': place['geometry']['location']
        } for place in places_data['results'][:5]]  # Limit to 5 results

        return jsonify({'stores': stores})

    except Exception as e:
        app.logger.error(f"Error finding liquor stores: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/register-event/<int:event_id>', methods=['POST'])
def register_event(event_id):
    event = Event.query.get_or_404(event_id)
    
    # בדיקה אם יש מקום בהתוועדות (רק אם יש הגבלת קיבולת)
    if event.capacity is not None:
        current_participants = EventRegistration.query.filter_by(event_id=event_id).count()
        if current_participants >= event.capacity:
            flash('מצטערים, ההתוועדות מלאה', 'error')
            return redirect(url_for('event_details', event_id=event_id))
    
    # המשך הרישום כרגיל
    registration = EventRegistration(
        event_id=event_id,
        user_id=current_user.id
    )
    db.session.add(registration)
    db.session.commit()
    
    flash('נרשמת בהצלחה להתוועדות!', 'success')
    return redirect(url_for('event_details', event_id=event_id))

@app.route('/import-data', methods=['GET'])
def import_data_route():
    try:
        with app.app_context():
            # יצירת הטבלאות
            db.create_all()
            
            # יצירת סיסמה חדשה
            admin_password = "Admin123!"  # סיסמה זמנית - תחליף אותה אחר כך
            password_hash = generate_password_hash(admin_password)
            
            # בדיקה אם המשתמש כבר קיים
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                # יצירת משתמש אדמין רדש
                admin = User(
                    username='admin',
                    email='motiwolff@gmail.com',
                    password_hash=password_hash,
                    is_admin=True
                )
                db.session.add(admin)
                db.session.commit()
                return f'Admin user created successfully! Username: admin, Password: {admin_password}'
            else:
                # עדכון סיסמה למשתמש קיים
                admin.password_hash = password_hash
                db.session.commit()
                return f'Admin password updated! Username: admin, Password: {admin_password}'
                
    except Exception as e:
        return f'Error: {str(e)}'

@app.route('/debug_admin')
def debug_admin():
    admin = User.query.filter_by(email='motiwolff@gmail.com').first()
    if admin:
        return jsonify({
            'exists': True,
            'username': admin.username,
            'email': admin.email,
            'is_admin': admin.is_admin,
            'has_password': bool(admin.password_hash)
        })
    return jsonify({'exists': False})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=environ.get('PORT', 5000))