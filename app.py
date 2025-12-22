from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_compress import Compress
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
from functools import wraps, lru_cache

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key-change-this')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# CORS configuration
CORS(app)

# Enable Gzip Compression
Compress(app)

# Cache configuration
cache = Cache(app, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300  # 5 minutes
})

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# MongoDB configuration with connection pooling
mongo_client = MongoClient(
    os.getenv('MONGO_URI'),
    maxPoolSize=50,
    minPoolSize=10,
    maxIdleTimeMS=30000,
    serverSelectionTimeoutMS=5000
)
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

# Create comprehensive indexes for better performance
users_collection.create_index([('email', ASCENDING)], unique=True)
jobs_collection.create_index([('posted_at', DESCENDING)])
jobs_collection.create_index([('job_type', ASCENDING), ('posted_at', DESCENDING)])
jobs_collection.create_index([('location', ASCENDING), ('posted_at', DESCENDING)])
jobs_collection.create_index([('company_name', 'text'), ('role', 'text'), ('description', 'text')])
workshops_collection.create_index([('posted_at', DESCENDING)])
workshops_collection.create_index([('name', 'text'), ('organizer', 'text')])
courses_collection.create_index([('posted_at', DESCENDING)])
courses_collection.create_index([('name', 'text'), ('instructor', 'text')])
hackathons_collection.create_index([('posted_at', DESCENDING)])
hackathons_collection.create_index([('name', 'text'), ('organizer', 'text')])
ads_collection.create_index([('active', ASCENDING), ('clicks', ASCENDING)])

# Cloudinary configuration with optimization defaults
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Admin credentials
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# Constants
ITEMS_PER_PAGE = 30
CACHE_TIMEOUT = 300  # 5 minutes

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

@lru_cache(maxsize=128)
def time_ago(posted_at_str):
    """Convert datetime to relative time string with caching"""
    if isinstance(posted_at_str, str):
        posted_at = datetime.fromisoformat(posted_at_str)
    else:
        posted_at = posted_at_str
    
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
    """Upload file to Cloudinary with optimizations"""
    try:
        result = cloudinary.uploader.upload(
            file,
            folder="community_platform",
            quality="auto:good",
            fetch_format="auto",
            width=800,
            crop="limit"
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

def get_pagination_data(page, total_items):
    """Calculate pagination data"""
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    has_prev = page > 1
    has_next = page < total_pages
    return {
        'page': page,
        'total_pages': total_pages,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_page': page - 1 if has_prev else None,
        'next_page': page + 1 if has_next else None
    }

# Authentication Routes
@app.route('/')
def index():
    return redirect(url_for('jobs'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('is_admin') else 'user_dashboard'))

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
        
        # Check user login - only fetch necessary fields
        user = users_collection.find_one(
            {'email': email},
            {'password': 1, 'name': 1}
        )
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['is_admin'] = False
            session['username'] = user['name']
            flash('Login successful!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('user_dashboard'))
        
        flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('is_admin') else 'user_dashboard'))

    if request.method == 'POST':
        name = sanitize_input(request.form.get('name', '').strip())
        email = sanitize_input(request.form.get('email', '').strip().lower())
        password = request.form.get('password', '')
        college = sanitize_input(request.form.get('college', '').strip())
        phone = sanitize_input(request.form.get('phone', '').strip())
        
        if not all([name, email, password, college]):
            flash('All fields are required', 'danger')
            return render_template('register.html')
        
        if not validate_email(email):
            flash('Invalid email format', 'danger')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return render_template('register.html')
        
        # Check if user exists - only check email field
        if users_collection.find_one({'email': email}, {'_id': 1}):
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
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
        
        session['user_id'] = str(result.inserted_id)
        session['is_admin'] = False
        session['username'] = name
        
        flash('Registration successful!', 'success')
        return redirect(url_for('user_dashboard'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

# User Dashboard
@app.route('/dashboard')
@login_required
def user_dashboard():
    # Only fetch necessary fields
    user = users_collection.find_one(
        {'_id': ObjectId(session['user_id'])},
        {'password': 0}  # Exclude password
    )
    return render_template('user_dashboard.html', user=user)

# Admin Dashboard
@app.route('/admin/dashboard')
@admin_required
@cache.cached(timeout=60)  # Cache for 1 minute
def admin_dashboard():
    """Admin dashboard with cached statistics"""
    stats = {
        'total_users': users_collection.estimated_document_count(),
        'total_jobs': jobs_collection.estimated_document_count(),
        'total_workshops': workshops_collection.estimated_document_count(),
        'total_courses': courses_collection.estimated_document_count(),
        'total_hackathons': hackathons_collection.estimated_document_count(),
        'total_roadmaps': roadmaps_collection.estimated_document_count(),
        'total_websites': websites_collection.estimated_document_count(),
        'total_ads': ads_collection.estimated_document_count(),
        'active_ads': ads_collection.count_documents({'active': True}),
        'total_ad_clicks': ad_clicks_collection.estimated_document_count()
    }
    return render_template('admin_dashboard.html', stats=stats)

@app.route('/admin/users')
@admin_required
def admin_users():
    """View paginated users"""
    page = request.args.get('page', 1, type=int)
    skip = (page - 1) * ITEMS_PER_PAGE
    
    total_users = users_collection.estimated_document_count()
    users = list(users_collection.find(
        {},
        {'password': 0}  # Exclude passwords
    ).sort('created_at', DESCENDING).skip(skip).limit(ITEMS_PER_PAGE))
    
    pagination = get_pagination_data(page, total_users)
    return render_template('admin_dashboard.html', users=users, section='users', pagination=pagination)

@app.route('/admin/content/<content_type>')
@admin_required
def admin_content(content_type):
    """View paginated content by type"""
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
    
    page = request.args.get('page', 1, type=int)
    skip = (page - 1) * ITEMS_PER_PAGE
    
    collection = collection_map[content_type]
    total_items = collection.estimated_document_count()
    content = list(collection.find().sort('posted_at', DESCENDING).skip(skip).limit(ITEMS_PER_PAGE))
    
    pagination = get_pagination_data(page, total_items)
    return render_template('admin_dashboard.html', content=content, content_type=content_type, section='content', pagination=pagination)

@app.route('/admin/add/<content_type>', methods=['POST'])
@admin_required
def admin_add_content(content_type):
    """Add new content and clear cache"""
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
    
    # Sanitize inputs
    for key in data:
        if isinstance(data[key], str):
            data[key] = sanitize_input(data[key])
            data[key] = set_default_value(data[key])
    
    data['posted_at'] = datetime.utcnow()
    data['admin_id'] = session['user_id']
    
    promote_as_ad = request.form.get('promote_as_ad') == 'on'
    
    if 'certification' in data:
        data['certification'] = data['certification'] == 'on'
    if 'active' in data:
        data['active'] = data['active'] == 'on'
    
    if 'requirements' in data and data['requirements'] != 'N/A':
        data['requirements'] = [r.strip() for r in data['requirements'].split(',') if r.strip()]
    
    result = collection_map[content_type].insert_one(data)
    
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
    
    # Clear relevant caches
    cache.delete_memoized(get_cached_content, content_type, 1)
    cache.clear()
    
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
        
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                image_url = upload_to_cloudinary(file)
                if image_url:
                    data['image'] = image_url
        
        promote_as_ad = request.form.get('promote_as_ad') == 'on'
        
        if 'promote_as_ad' in data:
            del data['promote_as_ad']
        
        for key in list(data.keys()):
            if isinstance(data[key], str):
                data[key] = sanitize_input(data[key])
                data[key] = set_default_value(data[key])
        
                if 'certification' in data:
                    data['certification'] = data['certification'] == 'on'
                else:
                    data['certification'] = False

                if 'active' in data:
                    data['active'] = data['active'] == 'on'
                else:
                    data['active'] = False

                if 'is_project' in data:
                    data['is_project'] = data['is_project'] == 'on'
                else:
                    data['is_project'] = False
        
        if 'requirements' in data and data['requirements'] != 'N/A':
            data['requirements'] = [r.strip() for r in data['requirements'].split(',') if r.strip()]
        
        data['updated_at'] = datetime.utcnow()
        
        collection.update_one({'_id': ObjectId(id)}, {'$set': data})
        
        if content_type in ['jobs', 'workshops', 'courses', 'hackathons']:
            if promote_as_ad:
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
                
                existing_ad = ads_collection.find_one({'content_reference': ObjectId(id)}, {'_id': 1})
                
                if existing_ad:
                    ads_collection.update_one({'_id': existing_ad['_id']}, {'$set': ad_data})
                    flash(f'{content_type.capitalize()} and ad updated successfully!', 'success')
                else:
                    ad_data['clicks'] = 0
                    ad_data['impressions'] = 0
                    ad_data['posted_at'] = datetime.utcnow()
                    ads_collection.insert_one(ad_data)
                    flash(f'{content_type.capitalize()} updated and ad created!', 'success')
            else:
                result = ads_collection.delete_many({'content_reference': ObjectId(id)})
                if result.deleted_count > 0:
                    flash(f'{content_type.capitalize()} updated (ad removed)!', 'success')
                else:
                    flash(f'{content_type.capitalize()} updated successfully!', 'success')
        else:
            flash(f'{content_type.capitalize()} updated successfully!', 'success')
        
        # Clear caches
        cache.delete_memoized(get_cached_content, content_type, 1)
        cache.clear()
        
        return redirect(url_for('admin_content', content_type=content_type))
    
    item = collection.find_one({'_id': ObjectId(id)})
    
    if content_type in ['jobs', 'workshops', 'courses', 'hackathons']:
        existing_ad = ads_collection.find_one({'content_reference': ObjectId(id)}, {'_id': 1})
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
    
    collection_map[content_type].delete_one({'_id': ObjectId(id)})
    ads_collection.delete_many({'content_reference': ObjectId(id)})
    
    # Clear caches
    cache.delete_memoized(get_cached_content, content_type, 1)
    cache.clear()
    
    flash(f'{content_type.capitalize()} deleted successfully!', 'success')
    return redirect(url_for('admin_content', content_type=content_type))

# Cached content fetching
@cache.memoize(timeout=CACHE_TIMEOUT)
def get_cached_content(content_type, page=1):
    """Get cached paginated content"""
    collection_map = {
        'jobs': jobs_collection,
        'workshops': workshops_collection,
        'courses': courses_collection,
        'hackathons': hackathons_collection
    }
    
    if content_type not in collection_map:
        return [], 0
    
    skip = (page - 1) * ITEMS_PER_PAGE
    collection = collection_map[content_type]
    
    # Use projection to exclude unnecessary fields
    items = list(collection.find(
        {},
        {'admin_id': 0}  # Exclude admin_id from public view
    ).sort('posted_at', DESCENDING).skip(skip).limit(ITEMS_PER_PAGE))
    
    total = collection.estimated_document_count()
    
    return items, total

# Public Content Pages with Pagination
@app.route('/jobs')
def jobs():
    """Jobs and internships page with pagination"""
    page = request.args.get('page', 1, type=int)
    all_jobs, total = get_cached_content('jobs', page)
    
    for job in all_jobs:
        job['time_ago'] = time_ago(str(job['posted_at']))
    
    pagination = get_pagination_data(page, total)
    return render_template('jobs.html', jobs=all_jobs, pagination=pagination)

@app.route('/workshops')
def workshops():
    """Workshops page with pagination"""
    page = request.args.get('page', 1, type=int)
    all_workshops, total = get_cached_content('workshops', page)
    
    for workshop in all_workshops:
        workshop['time_ago'] = time_ago(str(workshop['posted_at']))
    
    pagination = get_pagination_data(page, total)
    return render_template('workshops.html', workshops=all_workshops, pagination=pagination)

@app.route('/courses')
def courses():
    """Courses page with pagination"""
    page = request.args.get('page', 1, type=int)
    all_courses, total = get_cached_content('courses', page)
    
    for course in all_courses:
        course['time_ago'] = time_ago(str(course['posted_at']))
    
    pagination = get_pagination_data(page, total)
    return render_template('courses.html', courses=all_courses, pagination=pagination)

@app.route('/hackathons')
def hackathons():
    """Hackathons page with pagination"""
    page = request.args.get('page', 1, type=int)
    all_hackathons, total = get_cached_content('hackathons', page)
    
    for hackathon in all_hackathons:
        hackathon['time_ago'] = time_ago(str(hackathon['posted_at']))
    
    pagination = get_pagination_data(page, total)
    return render_template('hackathons.html', hackathons=all_hackathons, pagination=pagination)

@app.route('/roadmaps')
@login_required
def roadmaps():
    """Roadmaps page"""
    all_roadmaps = list(roadmaps_collection.find({}, {'admin_id': 0}))
    return render_template('roadmaps.html', roadmaps=all_roadmaps)

@app.route('/websites')
def websites():
    """Static websites page"""
    all_websites = list(websites_collection.find({}, {'admin_id': 0}))
    return render_template('websites.html', websites=all_websites)

@app.route('/our-projects')
def our_projects():
    """Community projects page"""
    projects = list(websites_collection.find({'is_project': True}, {'admin_id': 0}))
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
    
    item = collection_map[content_type].find_one({'_id': ObjectId(id)}, {'admin_id': 0})
    if not item:
        flash('Content not found', 'danger')
        return redirect(url_for('index'))
    
    item['time_ago'] = time_ago(str(item['posted_at']))
    
    # Get related content - limit fields and results
    if content_type == 'job':
        related = list(collection_map[content_type].find(
            {
                'job_type': item.get('job_type'),
                '_id': {'$ne': ObjectId(id)}
            },
            {'company_name': 1, 'role': 1, 'location': 1, 'posted_at': 1, 'image': 1}
        ).limit(3))
    else:
        related = list(collection_map[content_type].find(
            {'_id': {'$ne': ObjectId(id)}},
            {'name': 1, 'organizer': 1, 'posted_at': 1, 'image': 1}
        ).limit(3))
    
    return render_template('detail_page.html', item=item, content_type=content_type, related=related)

# Apply Actions
@app.route('/apply/<content_type>/<id>', methods=['POST'])
@login_required
def apply_content(content_type, id):
    """Handle apply action"""
    collection_map = {
        'job': jobs_collection,
        'workshop': workshops_collection,
        'course': courses_collection,
        'hackathon': hackathons_collection
    }
    
    if content_type not in collection_map:
        return jsonify({'error': 'Invalid content type'}), 400
    
    item = collection_map[content_type].find_one({'_id': ObjectId(id)}, {'official_link': 1})
    if not item:
        return jsonify({'error': 'Content not found'}), 404
    
    return jsonify({'redirect_url': item.get('official_link', '#')})

# Ad tracking
@app.route('/ad/impression/<ad_id>', methods=['POST'])
def ad_impression(ad_id):
    """Track ad impressions"""
    try:
        if not ObjectId.is_valid(ad_id):
            return jsonify({'success': False, 'error': 'Invalid ad ID'}), 400
            
        result = ads_collection.update_one(
            {'_id': ObjectId(ad_id)},
            {'$inc': {'impressions': 1}}
        )
        
        if result.matched_count == 0:
            return jsonify({'success': False, 'error': 'Ad not found'}), 404
            
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Ad impression error: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@app.route('/ad/click/<ad_id>', methods=['POST'])
def ad_click(ad_id):
    """Track ad clicks"""
    try:
        if not ObjectId.is_valid(ad_id):
            return jsonify({'success': False, 'error': 'Invalid ad ID'}), 400
            
        result = ads_collection.update_one(
            {'_id': ObjectId(ad_id)},
            {'$inc': {'clicks': 1}}
        )
        
        if result.matched_count == 0:
            return jsonify({'success': False, 'error': 'Ad not found'}), 404
        
        ad_clicks_collection.insert_one({
            'ad_id': ObjectId(ad_id),
            'clicked_at': datetime.utcnow(),
            'user_id': session.get('user_id'),
            'ip_address': request.remote_addr
        })
        
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Ad click error: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500


@app.route('/api/get-ads')
def get_ads():  # Note: Removed caching for true rotation
    """Get active ads in rotating order"""
    try:
        # Use MongoDB aggregation with $sample for random selection
        ads = list(ads_collection.aggregate([
            {'$match': {'active': True}},
            {'$sample': {'size': 5}},
            {'$project': {
                'title': 1, 
                'description': 1, 
                'image': 1, 
                'link': 1, 
                'clicks': 1
            }}
        ]))
        
        # Convert ObjectIds to strings
        for ad in ads:
            ad['_id'] = str(ad['_id'])
            if 'content_reference' in ad:
                ad['content_reference'] = str(ad['content_reference'])
            ad['title'] = ad.get('title', 'Opportunity')
            ad['description'] = ad.get('description', '')
            ad['image'] = ad.get('image', '')
            ad['link'] = ad.get('link', '#')
        
        return jsonify(ads)
    except Exception as e:
        print(f"Get ads error: {e}")
        return jsonify([])
        
        return jsonify(ads)
    except Exception as e:
        print(f"Get ads error: {e}")
        return jsonify([])

# Filters & Search with optimized queries
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
    
    # Pagination for filter results
    page = request.args.get('page', 1, type=int)
    skip = (page - 1) * ITEMS_PER_PAGE
    
    # Execute query with projection
    results = list(collection_map[content_type].find(
        query,
        {'admin_id': 0}
    ).sort('posted_at', DESCENDING).skip(skip).limit(ITEMS_PER_PAGE))
    
    for item in results:
        item['_id'] = str(item['_id'])
        item['time_ago'] = time_ago(str(item['posted_at']))
    
    return jsonify(results)

@app.route('/api/search')
def search():
    """Global search across all content with text indexes"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify([])
    
    results = []
    
    # Use text search indexes for better performance
    search_query = {'$text': {'$search': query}}
    projection = {'score': {'$meta': 'textScore'}, 'admin_id': 0}
    
    # Search in jobs
    try:
        jobs = list(jobs_collection.find(
            search_query,
            projection
        ).sort([('score', {'$meta': 'textScore'})]).limit(5))
        
        for job in jobs:
            job['_id'] = str(job['_id'])
            job['type'] = 'job'
            results.append(job)
    except:
        # Fallback to regex if text index not available
        jobs = list(jobs_collection.find({
            '$or': [
                {'company_name': {'$regex': query, '$options': 'i'}},
                {'role': {'$regex': query, '$options': 'i'}},
                {'job_type': {'$regex': query, '$options': 'i'}}
            ]
        }, {'admin_id': 0}).limit(5))
        
        for job in jobs:
            job['_id'] = str(job['_id'])
            job['type'] = 'job'
            results.append(job)
    
    # Search in workshops
    try:
        workshops = list(workshops_collection.find(
            search_query,
            projection
        ).sort([('score', {'$meta': 'textScore'})]).limit(5))
        
        for workshop in workshops:
            workshop['_id'] = str(workshop['_id'])
            workshop['type'] = 'workshop'
            results.append(workshop)
    except:
        workshops = list(workshops_collection.find({
            '$or': [
                {'name': {'$regex': query, '$options': 'i'}},
                {'organizer': {'$regex': query, '$options': 'i'}}
            ]
        }, {'admin_id': 0}).limit(5))
        
        for workshop in workshops:
            workshop['_id'] = str(workshop['_id'])
            workshop['type'] = 'workshop'
            results.append(workshop)
    
    # Search in courses
    try:
        courses = list(courses_collection.find(
            search_query,
            projection
        ).sort([('score', {'$meta': 'textScore'})]).limit(5))
        
        for course in courses:
            course['_id'] = str(course['_id'])
            course['type'] = 'course'
            results.append(course)
    except:
        courses = list(courses_collection.find({
            '$or': [
                {'name': {'$regex': query, '$options': 'i'}},
                {'instructor': {'$regex': query, '$options': 'i'}}
            ]
        }, {'admin_id': 0}).limit(5))
        
        for course in courses:
            course['_id'] = str(course['_id'])
            course['type'] = 'course'
            results.append(course)
    
    # Search in hackathons
    try:
        hackathons = list(hackathons_collection.find(
            search_query,
            projection
        ).sort([('score', {'$meta': 'textScore'})]).limit(5))
        
        for hackathon in hackathons:
            hackathon['_id'] = str(hackathon['_id'])
            hackathon['type'] = 'hackathon'
            results.append(hackathon)
    except:
        hackathons = list(hackathons_collection.find({
            '$or': [
                {'name': {'$regex': query, '$options': 'i'}},
                {'organizer': {'$regex': query, '$options': 'i'}}
            ]
        }, {'admin_id': 0}).limit(5))
        
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
    return time_ago(str(dt))

# Cache control for static files
@app.after_request
def add_header(response):
    """Add cache headers for static files"""
    if 'static' in request.path:
        response.cache_control.max_age = 31536000  # 1 year
        response.cache_control.public = True
    elif request.endpoint in ['jobs', 'workshops', 'courses', 'hackathons']:
        response.cache_control.max_age = 300  # 5 minutes
        response.cache_control.public = True
    return response

if __name__ == '__main__':

    app.run(debug=True, host='0.0.0.0', port=5000)
