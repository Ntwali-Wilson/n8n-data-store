import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# --- CONFIGURATION ---
app = Flask(__name__)
app.secret_key = "IsomoLink_Secret_Key_2026" # Change this in production
# Use SQLite for local testing, PostgreSQL for Render
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///isomolink.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATABASE MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False) # Plain text for MVP demo only
    role = db.Column(db.String(20), nullable=False) # 'student', 'teacher'
    full_name = db.Column(db.String(100))
    
    # Relationships
    grades = db.relationship('Grade', backref='student', lazy=True)

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False) # e.g., "Mathematics"
    score = db.Column(db.Float, nullable=False) # e.g., 85.5
    weight = db.Column(db.Float, default=1.0) # 1.0 = Exam, 0.5 = Quiz

# --- HELPER FUNCTIONS ---

def calculate_gpa(user_id):
    """
    Calculates the weighted average grade dynamically from the database.
    This is NOT a fixed number; it runs every time the dashboard loads.
    """
    grades = Grade.query.filter_by(student_id=user_id).all()
    if not grades:
        return 0.0
    
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        # In a real app, hash passwords!
        user = User.query.filter_by(username=username).first()
        
        if user: # Simplified login for demo
            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            return redirect(url_for('dashboard'))
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    # DYNAMIC DATA PACKAGING
    context = {
        "user": user,
        "role": user.role
    }
    
    if user.role == 'student':
        # Calculate grades in real-time
        context['gpa'] = calculate_gpa(user_id)
        context['grades'] = Grade.query.filter_by(student_id=user_id).all()
        
    elif user.role == 'teacher':
        # Fetch analytics
        context['total_students'] = User.query.filter_by(role='student').count()
        context['revenue'] = 45000 # Dummy revenue for now

    return render_template('dashboard.html', **context)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- SETUP SCRIPT ---
# Run this once to create dummy data
@app.route('/setup')
def setup():
    db.create_all()
    
    # Create Dummy Student
    if not User.query.filter_by(username='student1').first():
        s1 = User(username='student1', password='123', role='student', full_name='Jane Doe')
        db.session.add(s1)
        db.session.commit()
        
        # Add Grades for calculation
        db.session.add(Grade(student_id=s1.id, subject='Math', score=85, weight=1.0))
        db.session.add(Grade(student_id=s1.id, subject='Physics', score=72, weight=1.0))
        db.session.add(Grade(student_id=s1.id, subject='Quiz 1', score=90, weight=0.5))
        db.session.commit()

    # Create Dummy Teacher
    if not User.query.filter_by(username='teacher1').first():
        t1 = User(username='teacher1', password='123', role='teacher', full_name='Mr. John')
        db.session.add(t1)
        db.session.commit()

    return "Database Created & Dummy Data Added!"

if __name__ == '__main__':
    app.run(debug=True)
