import os
from sqlalchemy.sql import func
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURATION ---
# Database Connection
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'IsomoLink_Fallback_Key') # vital for sessions

db = SQLAlchemy(app)

# --- MODELS (The Database Structure) ---
class User(db.Model):
    __tablename__ = 'users' # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False) # The Handle
    email = db.Column(db.String(120), unique=True, nullable=False)   # NEW: Real Email
    password_hash = db.Column(db.String(255), nullable=False)        # NEW: Secure Hash
    role = db.Column(db.String(20), default='student') # student, teacher, school
    
    # Relationships
    grades = db.relationship('Grade', backref='student', lazy=True)
    
    # Security Helpers
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Grade(db.Model):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Float, nullable=False)
    weight = db.Column(db.Float, default=1.0)

# --- HELPER FUNCTIONS ---
def calculate_gpa(user_id):
    grades = Grade.query.filter_by(student_id=user_id).all()
    if not grades: return 0.0
    total_score = sum(g.score * g.weight for g in grades)
    total_weight = sum(g.weight for g in grades)
    if total_weight == 0: return 0.0
    return round(total_score / total_weight, 1)

# --- ROUTES ---

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# 1. REAL REGISTRATION (New Feature)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get and clean data
        username = request.form['username'].lower().strip()
        email = request.form['email'].lower().strip()
        password = request.form['password']
        role = request.form['role']
        
        # Check if user exists
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Error: Username or Email is already taken!', 'danger')
            return redirect(url_for('register'))
        
        # Create and Save
        new_user = User(username=username, email=email, role=role)
        new_user.set_password(password) # Encrypts the password
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('auth/register.html')

# 2. REAL LOGIN (Updated Security)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].lower().strip()
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        # Verify Password Hash
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('auth/login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_user = User.query.get(session['user_id'])
    
    context = {
        "user": current_user,
        "role": current_user.role
    }
    
    if current_user.role == 'student':
        # 1. Calculate MY GPA
        context['gpa'] = calculate_gpa(current_user.id)
        
        # 2. Get MY Grades
        context['grades'] = Grade.query.filter_by(student_id=current_user.id).all()
        
        # 3. NEW FEATURE: The Leaderboard Query
        # This fetches the Top 5 Students by Average Score
        leaderboard_data = db.session.query(
            User.username,
            func.avg(Grade.score).label('avg_score')
        ).join(Grade).filter(User.role == 'student').group_by(User.id).order_by(func.avg(Grade.score).desc()).limit(5).all()
        
        context['leaderboard'] = leaderboard_data

    elif current_user.role == 'teacher':
        context['total_students'] = User.query.filter_by(role='student').count()
        # You can add a "Top Selling Teachers" leaderboard here later
    
    return render_template('dashboard.html', **context)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- DB INIT (Run Once) ---
@app.route('/init-db')
def init_db():
    db.create_all()
    return "Database Tables Re-Created Successfully!"

if __name__ == '__main__':
    app.run(debug=True)
