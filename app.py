from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv
import os
import re
from functools import wraps


# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key-change-this')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# CORS configuration
CORS(app)

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# MongoDB configuration
mongo_client = MongoClient(os.getenv('MONGO_URI'))
db = mongo_client['community_platform']

# Collections
users_collection = db['users']
jobs_collection = db['jobs_internships']
workshops_collection = db['workshops']
courses_collection = db['courses']
hackathons_collection = db['hackathons']
roadmaps_collection = db['roadmaps']
websites_collection = db['websites']
ads_collection = db['advertisements']
ad_clicks_collection = db['ad_clicks']

# Create indexes for better performance
users_collection.create_index([('email', ASCENDING)], unique=True)
jobs_collection.create_index([('posted_at', DESCENDING)])
jobs_collection.create_index([('job_type', ASCENDING)])
jobs_collection.create_index([('location', ASCENDING)])
workshops_collection.create_index([('posted_at', DESCENDING)])
courses_collection.create_index([('posted_at', DESCENDING)])
hackathons_collection.create_index([('posted_at', DESCENDING)])

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Admin credentials
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')  # Should be hashed in production

# Helper Functions
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Admin access required', 'danger')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def time_ago(posted_at):
    """Convert datetime to relative time string"""
    if isinstance(posted_at, str):
        posted_at = datetime.fromisoformat(posted_at)
    
    now = datetime.utcnow()
    diff = now - posted_at
    
    seconds = diff.total_seconds()
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    else:
        months = int(seconds / 2592000)
        return f"{months} month{'s' if months > 1 else ''} ago"

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def sanitize_input(text):
    """Sanitize user input to prevent XSS"""
    if not text:
        return text
    return text.replace('<', '&lt;').replace('>', '&gt;')

def upload_to_cloudinary(file):
    """Upload file to Cloudinary and return URL"""
    try:
        result = cloudinary.uploader.upload(
            file,
            folder="community_platform",
            quality="auto",
            fetch_format="auto"
        )
        return result['secure_url']
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None

def set_default_value(value, default="N/A"):
    """Set default value if field is empty"""
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return default
    return value

# Authentication Routes
@app.route('/')
def index():
    '''if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('is_admin') else 'user_dashboard'))
    
    """Landing page"""
    stats = {
        'total_jobs': jobs_collection.count_documents({}),
        'total_users': users_collection.count_documents({}),
        'total_opportunities': (
            jobs_collection.count_documents({}) +
            workshops_collection.count_documents({}) +
            courses_collection.count_documents({}) +
            hackathons_collection.count_documents({})
        )
    }'''
    return redirect(url_for('jobs'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    # Prevent logged-in users from accessing login page
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('is_admin') else 'user_dashboard'))

    """Login page for both admin and users"""
    if request.method == 'POST':
        email = sanitize_input(request.form.get('email', '').strip())
        password = request.form.get('password', '')
        
        # Check if admin login
        if email == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['user_id'] = 'admin'
            session['is_admin'] = True
            session['username'] = 'Admin'
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        
        # Check user login
        user = users_collection.find_one({'email': email})
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['is_admin'] = False
            session['username'] = user['name']
            flash('Login successful!', 'success')
            
            # Redirect to intended page or dashboard
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('user_dashboard'))
        
        flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    # Prevent logged-in users from accessing register page
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('is_admin') else 'user_dashboard'))

    """User registration"""
    if request.method == 'POST':
        name = sanitize_input(request.form.get('name', '').strip())
        email = sanitize_input(request.form.get('email', '').strip().lower())
        password = request.form.get('password', '')
        college = sanitize_input(request.form.get('college', '').strip())
        phone = sanitize_input(request.form.get('phone', '').strip())
        
        # Validation
        if not all([name, email, password, college]):
            flash('All fields are required', 'danger')
            return render_template('register.html')
        
        if not validate_email(email):
            flash('Invalid email format', 'danger')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return render_template('register.html')
        
        # Check if user already exists
        if users_collection.find_one({'email': email}):
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        # Create user
        hashed_password = generate_password_hash(password)
        user_data = {
            'name': name,
            'email': email,
            'password': hashed_password,
            'college': college,
            'phone': phone,
            'created_at': datetime.utcnow(),
            'profile_picture': None
        }
        
        result = users_collection.insert_one(user_data)
        
        # Auto login
        session['user_id'] = str(result.inserted_id)
        session['is_admin'] = False
        session['username'] = name
        
        flash('Registration successful!', 'success')
        return redirect(url_for('user_dashboard'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

# User Dashboard
@app.route('/dashboard')
@login_required
def user_dashboard():
    """User dashboard"""
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    return render_template('user_dashboard.html', user=user)

# Admin Dashboard
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard with statistics"""
    stats = {
        'total_users': users_collection.count_documents({}),
        'total_jobs': jobs_collection.count_documents({}),
        'total_workshops': workshops_collection.count_documents({}),
        'total_courses': courses_collection.count_documents({}),
        'total_hackathons': hackathons_collection.count_documents({}),
        'total_roadmaps': roadmaps_collection.count_documents({}),
        'total_websites': websites_collection.count_documents({}),
        'total_ads': ads_collection.count_documents({}),
        'active_ads': ads_collection.count_documents({'active': True}),
        'total_ad_clicks': ad_clicks_collection.count_documents({})
    }
    return render_template('admin_dashboard.html', stats=stats)

@app.route('/admin/users')
@admin_required
def admin_users():
    """View all users"""
    users = list(users_collection.find().sort('created_at', DESCENDING))
    return render_template('admin_dashboard.html', users=users, section='users')

@app.route('/admin/content/<content_type>')
@admin_required
def admin_content(content_type):
    """View content by type"""
    collection_map = {
        'jobs': jobs_collection,
        'workshops': workshops_collection,
        'courses': courses_collection,
        'hackathons': hackathons_collection,
        'roadmaps': roadmaps_collection,
        'websites': websites_collection,
        'ads': ads_collection
    }
    
    if content_type not in collection_map:
        flash('Invalid content type', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    content = list(collection_map[content_type].find().sort('posted_at', DESCENDING))
    return render_template('admin_dashboard.html', content=content, content_type=content_type, section='content')

@app.route('/admin/add/<content_type>', methods=['POST'])
@admin_required
def admin_add_content(content_type):
    """Add new content"""
    collection_map = {
        'jobs': jobs_collection,
        'workshops': workshops_collection,
        'courses': courses_collection,
        'hackathons': hackathons_collection,
        'roadmaps': roadmaps_collection,
        'websites': websites_collection,
        'ads': ads_collection
    }
    
    if content_type not in collection_map:
        return jsonify({'error': 'Invalid content type'}), 400
    
    data = request.form.to_dict()
    
    # Handle file upload
    if 'image' in request.files:
        file = request.files['image']
        if file.filename:
            image_url = upload_to_cloudinary(file)
            data['image'] = image_url
    
    # Sanitize inputs and set defaults
    for key in data:
        if isinstance(data[key], str):
            data[key] = sanitize_input(data[key])
            data[key] = set_default_value(data[key])
    
    # Add metadata
    data['posted_at'] = datetime.utcnow()
    data['admin_id'] = session['user_id']
    
    # Check if promote_as_ad is checked
    promote_as_ad = request.form.get('promote_as_ad') == 'on'
    
    # Convert checkboxes to boolean
    if 'certification' in data:
        data['certification'] = data['certification'] == 'on'
    if 'active' in data:
        data['active'] = data['active'] == 'on'
    
    # Handle arrays (requirements, tags, etc.)
    if 'requirements' in data and data['requirements'] != 'N/A':
        data['requirements'] = [r.strip() for r in data['requirements'].split(',') if r.strip()]
    
    # Insert into database
    result = collection_map[content_type].insert_one(data)
    
    # Create ad if promote_as_ad is checked
    if promote_as_ad:
        ad_data = {
            'title': data.get('company_name') or data.get('name') or data.get('title', 'N/A'),
            'description': data.get('role') or data.get('description', 'N/A')[:100],
            'image': data.get('image', ''),
            'link': data.get('official_link', '#'),
            'content_type': content_type,
            'content_reference': result.inserted_id,
            'active': True,
            'clicks': 0,
            'impressions': 0,
            'posted_at': datetime.utcnow(),
            'admin_id': session['user_id']
        }
        ads_collection.insert_one(ad_data)
    
    flash(f'{content_type.capitalize()} added successfully!', 'success')
    return redirect(url_for('admin_content', content_type=content_type))

@app.route('/admin/edit/<content_type>/<id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_content(content_type, id):
    """Edit existing content"""
    collection_map = {
        'jobs': jobs_collection,
        'workshops': workshops_collection,
        'courses': courses_collection,
        'hackathons': hackathons_collection,
        'roadmaps': roadmaps_collection,
        'websites': websites_collection,
        'ads': ads_collection
    }
    
    if content_type not in collection_map:
        flash('Invalid content type', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    collection = collection_map[content_type]
    
    if request.method == 'POST':
        data = request.form.to_dict()
        
        # Handle file upload
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                image_url = upload_to_cloudinary(file)
                if image_url:
                    data['image'] = image_url
        
        # Check promote_as_ad BEFORE sanitizing
        promote_as_ad = request.form.get('promote_as_ad') == 'on'
        
        # Remove promote_as_ad from data (it's not a field in the content document)
        if 'promote_as_ad' in data:
            del data['promote_as_ad']
        
        # Sanitize inputs and set defaults
        for key in list(data.keys()):
            if isinstance(data[key], str):
                data[key] = sanitize_input(data[key])
                data[key] = set_default_value(data[key])
        
        # Convert checkboxes
        if 'certification' in data:
            data['certification'] = data['certification'] == 'on'
        if 'active' in data:
            data['active'] = data['active'] == 'on'
        if 'is_project' in data:
            data['is_project'] = data['is_project'] == 'on'
        
        # Handle arrays (requirements, tags, etc.)
        if 'requirements' in data and data['requirements'] != 'N/A':
            data['requirements'] = [r.strip() for r in data['requirements'].split(',') if r.strip()]
        
        # Update timestamp
        data['updated_at'] = datetime.utcnow()
        
        # Update the content
        collection.update_one({'_id': ObjectId(id)}, {'$set': data})
        
        # Handle ad promotion for content types that support it
        if content_type in ['jobs', 'workshops', 'courses', 'hackathons']:
            if promote_as_ad:
                # Prepare ad data
                ad_data = {
                    'title': data.get('company_name') or data.get('name') or 'Opportunity',
                    'description': (data.get('role') or data.get('description', ''))[:150],
                    'image': data.get('image', ''),
                    'link': data.get('official_link', '#'),
                    'content_type': content_type,
                    'content_reference': ObjectId(id),
                    'active': True,
                    'updated_at': datetime.utcnow(),
                    'admin_id': session['user_id']
                }
                
                # Check if ad already exists
                existing_ad = ads_collection.find_one({'content_reference': ObjectId(id)})
                
                if existing_ad:
                    # Update existing ad
                    ads_collection.update_one(
                        {'_id': existing_ad['_id']},
                        {'$set': ad_data}
                    )
                    flash(f'{content_type.capitalize()} and ad updated successfully!', 'success')
                else:
                    # Create new ad
                    ad_data['clicks'] = 0
                    ad_data['impressions'] = 0
                    ad_data['posted_at'] = datetime.utcnow()
                    ads_collection.insert_one(ad_data)
                    flash(f'{content_type.capitalize()} updated and ad created!', 'success')
            else:
                # Delete associated ads if promote is unchecked
                result = ads_collection.delete_many({'content_reference': ObjectId(id)})
                if result.deleted_count > 0:
                    flash(f'{content_type.capitalize()} updated (ad removed)!', 'success')
                else:
                    flash(f'{content_type.capitalize()} updated successfully!', 'success')
        else:
            flash(f'{content_type.capitalize()} updated successfully!', 'success')
        
        return redirect(url_for('admin_content', content_type=content_type))
    
    # GET request - load the item
    item = collection.find_one({'_id': ObjectId(id)})
    
    # Check if this item has an associated ad
    if content_type in ['jobs', 'workshops', 'courses', 'hackathons']:
        existing_ad = ads_collection.find_one({'content_reference': ObjectId(id)})
        item['has_ad'] = existing_ad is not None
    else:
        item['has_ad'] = False
    
    return render_template('admin_dashboard.html', item=item, content_type=content_type, section='edit')

@app.route('/admin/delete/<content_type>/<id>', methods=['POST'])
@admin_required
def admin_delete_content(content_type, id):
    """Delete content and associated ads"""
    collection_map = {
        'jobs': jobs_collection,
        'workshops': workshops_collection,
        'courses': courses_collection,
        'hackathons': hackathons_collection,
        'roadmaps': roadmaps_collection,
        'websites': websites_collection,
        'ads': ads_collection
    }
    
    if content_type not in collection_map:
        return jsonify({'error': 'Invalid content type'}), 400
    
    # Delete the content
    collection_map[content_type].delete_one({'_id': ObjectId(id)})
    
    # Delete associated ads (cascade delete)
    ads_collection.delete_many({'content_reference': ObjectId(id)})
    
    flash(f'{content_type.capitalize()} deleted successfully!', 'success')
    return redirect(url_for('admin_content', content_type=content_type))

# Public Content Pages
@app.route('/jobs')
def jobs():
    """Jobs and internships page"""
    all_jobs = list(jobs_collection.find().sort('posted_at', DESCENDING))
    for job in all_jobs:
        job['time_ago'] = time_ago(job['posted_at'])
    return render_template('jobs.html', jobs=all_jobs)

@app.route('/workshops')
def workshops():
    """Workshops page"""
    all_workshops = list(workshops_collection.find().sort('posted_at', DESCENDING))
    for workshop in all_workshops:
        workshop['time_ago'] = time_ago(workshop['posted_at'])
    return render_template('workshops.html', workshops=all_workshops)

@app.route('/courses')
def courses():
    """Courses page"""
    all_courses = list(courses_collection.find().sort('posted_at', DESCENDING))
    for course in all_courses:
        course['time_ago'] = time_ago(course['posted_at'])
    return render_template('courses.html', courses=all_courses)

@app.route('/hackathons')
def hackathons():
    """Hackathons page"""
    all_hackathons = list(hackathons_collection.find().sort('posted_at', DESCENDING))
    for hackathon in all_hackathons:
        hackathon['time_ago'] = time_ago(hackathon['posted_at'])
    return render_template('hackathons.html', hackathons=all_hackathons)

@app.route('/roadmaps')
@login_required
def roadmaps():
    """Roadmaps page"""
    all_roadmaps = list(roadmaps_collection.find())
    return render_template('roadmaps.html', roadmaps=all_roadmaps)

@app.route('/websites')
def websites():
    """Static websites page"""
    all_websites = list(websites_collection.find())
    return render_template('websites.html', websites=all_websites)

@app.route('/our-projects')
def our_projects():
    """Community projects page"""
    projects = list(websites_collection.find({'is_project': True}))
    return render_template('our_projects.html', projects=projects)

# Detail Pages
@app.route('/detail/<content_type>/<id>')
@login_required
def detail_page(content_type, id):
    """Dynamic detail page for any content"""
    collection_map = {
        'job': jobs_collection,
        'workshop': workshops_collection,
        'course': courses_collection,
        'hackathon': hackathons_collection
    }
    
    if content_type not in collection_map:
        flash('Invalid content type', 'danger')
        return redirect(url_for('index'))
    
    item = collection_map[content_type].find_one({'_id': ObjectId(id)})
    if not item:
        flash('Content not found', 'danger')
        return redirect(url_for('index'))
    
    item['time_ago'] = time_ago(item['posted_at'])
    
    # Get related content (same job_type for jobs, or just recent for others)
    if content_type == 'job':
        related = list(collection_map[content_type].find({
            'job_type': item.get('job_type'),
            '_id': {'$ne': ObjectId(id)}
        }).limit(3))
    else:
        related = list(collection_map[content_type].find({
            '_id': {'$ne': ObjectId(id)}
        }).limit(3))
    
    return render_template('detail_page.html', item=item, content_type=content_type, related=related)

# Apply Actions (Protected)
@app.route('/apply/<content_type>/<id>', methods=['POST'])
@login_required
def apply_content(content_type, id):
    """Handle apply action - redirect to official link"""
    collection_map = {
        'job': jobs_collection,
        'workshop': workshops_collection,
        'course': courses_collection,
        'hackathon': hackathons_collection
    }
    
    if content_type not in collection_map:
        return jsonify({'error': 'Invalid content type'}), 400
    
    item = collection_map[content_type].find_one({'_id': ObjectId(id)})
    if not item:
        return jsonify({'error': 'Content not found'}), 404
    
    # Log the application (optional analytics)
    # You can track user applications here
    
    return jsonify({'redirect_url': item.get('official_link', '#')})

# Ad Tracking
@app.route('/ad/click/<ad_id>', methods=['POST'])
def ad_click(ad_id):
    """Track ad clicks"""
    try:
        # Update click count
        ads_collection.update_one(
            {'_id': ObjectId(ad_id)},
            {'$inc': {'clicks': 1}}
        )
        
        # Log the click
        ad_clicks_collection.insert_one({
            'ad_id': ObjectId(ad_id),
            'clicked_at': datetime.utcnow(),
            'user_id': session.get('user_id'),
            'ip_address': request.remote_addr
        })
        
        print(f"DEBUG: Ad {ad_id} clicked")  # Debug line
        return jsonify({'success': True})
    except Exception as e:
        print(f"Ad click error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/ad/impression/<ad_id>', methods=['POST'])
def ad_impression(ad_id):
    """Track ad impressions"""
    try:
        # Update impression count
        ads_collection.update_one(
            {'_id': ObjectId(ad_id)},
            {'$inc': {'impressions': 1}}
        )
        
        print(f"DEBUG: Ad {ad_id} impression tracked")  # Debug line
        return jsonify({'success': True})
    except Exception as e:
        print(f"Ad impression error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get-ads')
def get_ads():
    """Get active ads for display"""
    try:
        # Get active ads, sorted by clicks (least clicked first to give fair exposure)
        ads = list(ads_collection.find({'active': True}).sort('clicks', ASCENDING).limit(5))
        
        # Convert ObjectIds to strings
        for ad in ads:
            ad['_id'] = str(ad['_id'])
            if 'content_reference' in ad:
                ad['content_reference'] = str(ad['content_reference'])
            # Ensure all required fields exist
            ad['title'] = ad.get('title', 'Opportunity')
            ad['description'] = ad.get('description', '')
            ad['image'] = ad.get('image', '')
            ad['link'] = ad.get('link', '#')
        
        print(f"DEBUG: Returning {len(ads)} ads")  # Debug line
        return jsonify(ads)
    except Exception as e:
        print(f"Get ads error: {e}")
        return jsonify([])

# Filters & Search
@app.route('/api/filter/<content_type>')
def filter_content(content_type):
    """Filter content based on query parameters"""
    collection_map = {
        'jobs': jobs_collection,
        'workshops': workshops_collection,
        'courses': courses_collection,
        'hackathons': hackathons_collection
    }
    
    if content_type not in collection_map:
        return jsonify({'error': 'Invalid content type'}), 400
    
    # Build filter query
    query = {}
    
    if request.args.get('location'):
        query['location'] = {'$regex': request.args.get('location'), '$options': 'i'}
    
    if request.args.get('price'):
        query['price'] = request.args.get('price')
    
    if request.args.get('date'):
        date_filter = request.args.get('date')
        now = datetime.utcnow()
        if date_filter == '24h':
            query['posted_at'] = {'$gte': now - timedelta(hours=24)}
        elif date_filter == 'week':
            query['posted_at'] = {'$gte': now - timedelta(days=7)}
        elif date_filter == 'month':
            query['posted_at'] = {'$gte': now - timedelta(days=30)}
    
    if request.args.get('job_type'):
        query['job_type'] = request.args.get('job_type')
    
    if request.args.get('experience'):
        query['required_experience'] = request.args.get('experience')
    
    # Execute query
    results = list(collection_map[content_type].find(query).sort('posted_at', DESCENDING))
    
    for item in results:
        item['_id'] = str(item['_id'])
        item['time_ago'] = time_ago(item['posted_at'])
    
    return jsonify(results)

@app.route('/api/search')
def search():
    """Global search across all content"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify([])
    
    results = []
    
    # Search in jobs
    jobs = list(jobs_collection.find({
        '$or': [
            {'company_name': {'$regex': query, '$options': 'i'}},
            {'role': {'$regex': query, '$options': 'i'}},
            {'job_type': {'$regex': query, '$options': 'i'}},
            {'description': {'$regex': query, '$options': 'i'}}
        ]
    }).limit(5))
    
    for job in jobs:
        job['_id'] = str(job['_id'])
        job['type'] = 'job'
        results.append(job)
    
    # Search in workshops
    workshops = list(workshops_collection.find({
        '$or': [
            {'name': {'$regex': query, '$options': 'i'}},
            {'organizer': {'$regex': query, '$options': 'i'}}
        ]
    }).limit(5))
    
    for workshop in workshops:
        workshop['_id'] = str(workshop['_id'])
        workshop['type'] = 'workshop'
        results.append(workshop)
    
    # Search in courses
    courses = list(courses_collection.find({
        '$or': [
            {'name': {'$regex': query, '$options': 'i'}},
            {'instructor': {'$regex': query, '$options': 'i'}}
        ]
    }).limit(5))
    
    for course in courses:
        course['_id'] = str(course['_id'])
        course['type'] = 'course'
        results.append(course)
    
    # Search in hackathons
    hackathons = list(hackathons_collection.find({
        '$or': [
            {'name': {'$regex': query, '$options': 'i'}},
            {'organizer': {'$regex': query, '$options': 'i'}}
        ]
    }).limit(5))
    
    for hackathon in hackathons:
        hackathon['_id'] = str(hackathon['_id'])
        hackathon['type'] = 'hackathon'
        results.append(hackathon)
    
    return jsonify(results)

# Error Handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Template Filters
@app.template_filter('time_ago')
def time_ago_filter(dt):
    return time_ago(dt)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)