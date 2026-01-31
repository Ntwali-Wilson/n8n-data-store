import os
from sqlalchemy.sql import func
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import google.generativeai as genai
import markdown # To format the AI's response nicely

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
# --- NEW MODELS (Paste this below the User class) ---

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, default=0.0) # Price in RWF
    thumbnail_url = db.Column(db.String(255)) # Image for the dashboard card
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    lessons = db.relationship('Lesson', backref='course', lazy=True)
    # Make sure 'User' can access their courses
    teacher = db.relationship('User', backref=db.backref('courses_taught', lazy=True))

class Lesson(db.Model):
    __tablename__ = 'lessons'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    video_url = db.Column(db.String(255), nullable=False) # YouTube/Vimeo/Supabase Link
    duration = db.Column(db.String(20)) # e.g., "15:30"
    position = db.Column(db.Integer) # Order: 1, 2, 3
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)

# --- NEW MODEL: Chat History ---
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False) # 'user' or 'model'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
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
        
        # 3. Base Leaderboard Query (Group by User, Order by Avg Score)
        # We define the query once so we can use it twice
        leaderboard_query = db.session.query(
            User.username,
            User.id,
            func.avg(Grade.score).label('avg_score')
        ).join(Grade).filter(User.role == 'student').group_by(User.id).order_by(func.avg(Grade.score).desc())
        
        # A. Fetch Top 5 for the Widget
        context['leaderboard'] = leaderboard_query.limit(5).all()

        # B. Calculate MY RANK (The Logic Fix)
        # We need the full list to find where YOU stand
        all_ranked_students = leaderboard_query.all()
        
        my_rank = 0
        # Loop through everyone to find my position
        for index, student in enumerate(all_ranked_students):
            if student.id == current_user.id:
                my_rank = index + 1 # Rank is index + 1 (because index starts at 0)
                break
        
        # If I have no grades yet, I am unranked
        if my_rank == 0:
            my_rank = "--"
            
        context['my_rank'] = my_rank

    elif current_user.role == 'teacher':
        context['total_students'] = User.query.filter_by(role='student').count()
        # You can add revenue logic here later
    
    return render_template('dashboard.html', **context)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- COURSE ROUTES ---

# 1. Course Overview / Player
@app.route('/course/<int:course_id>')
def view_course(course_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    course = Course.query.get_or_404(course_id)
    # Default to the first lesson if none selected
    current_lesson = course.lessons[0] if course.lessons else None
    
    return render_template('course/player.html', course=course, current_lesson=current_lesson)

# 2. Watch Specific Lesson
@app.route('/course/<int:course_id>/lesson/<int:lesson_id>')
def watch_lesson(course_id, lesson_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    course = Course.query.get_or_404(course_id)
    current_lesson = Lesson.query.get_or_404(lesson_id)
    
    return render_template('course/player.html', course=course, current_lesson=current_lesson)

# 3. Create Dummy Course (Run this once via URL to test)
@app.route('/create-dummy-course')
def create_dummy_course():
    # Ensure Teacher Exists
    teacher = User.query.filter_by(role='teacher').first()
    if not teacher: return "Create a teacher account first!"

    # Create the Course (Bundle)
    forex_course = Course(
        title="Intro to Forex Trading",
        description="Master the currency markets. Learn leverage, pips, and risk management.",
        price=5000.0,
        teacher_id=teacher.id,
        thumbnail_url="https://images.unsplash.com/photo-1611974765270-ca1258634369?auto=format&fit=crop&w=500&q=60"
    )
    db.session.add(forex_course)
    db.session.commit()

    # Add Lessons
    lessons = [
        Lesson(title="What is Forex?", video_url="https://www.youtube.com/embed/f432H32", duration="10:00", position=1, course=forex_course),
        Lesson(title="Reading Candlesticks", video_url="https://www.youtube.com/embed/d3213", duration="15:30", position=2, course=forex_course),
        Lesson(title="Risk Management Strategy", video_url="https://www.youtube.com/embed/g5435", duration="20:00", position=3, course=forex_course)
    ]
    db.session.add_all(lessons)
    db.session.commit()
    
    return "Dummy Course 'Forex Trading' Created!"

@app.route('/leaderboard')
def leaderboard_page():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    # FETCH TOP 50 STUDENTS
    # We removed User.full_name to fix the error
    leaderboard_data = db.session.query(
        User.username,
        func.avg(Grade.score).label('avg_score')
    ).join(Grade).filter(User.role == 'student').group_by(User.id).order_by(func.avg(Grade.score).desc()).limit(50).all()
    
    return render_template('leaderboard.html', leaderboard=leaderboard_data)

# --- SEARCH ROUTE ---
@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    
    # If search is empty, go back
    if not query:
        return redirect(url_for('dashboard'))
    
    # 1. Search Courses (Title or Description)
    # ilike makes it case-insensitive (e.g., "forex" matches "Forex")
    courses = Course.query.filter(
        (Course.title.ilike(f'%{query}%')) | 
        (Course.description.ilike(f'%{query}%'))
    ).all()
    
    # 2. Search People (Students & Teachers)
    people = User.query.filter(
        (User.username.ilike(f'%{query}%')) |
        (User.full_name.ilike(f'%{query}%')) # Only if you added full_name column
    ).limit(10).all()
    
    return render_template('search_results.html', query=query, courses=courses, people=people)
# --- AI CONFIGURATION ---
# Replace 'YOUR_API_KEY' with your actual key from Google AI Studio
os.environ["GEMINI_API_KEY"] = "AIzaSyA_-UfBzXP1R957RjgKnX4tmJLHJsHldOUE" 
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Set up the model
model = genai.GenerativeModel('gemini-pro')
@app.route('/school/green-hills')
def school_profile():
    return render_template('school_profile.html')

# --- SMART AI CHAT ROUTE ---
@app.route('/api/chat', methods=['POST'])
def chat_with_tutor():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    user_text = data.get('message')
    user_id = session['user_id']

    # 1. Save User Message to DB
    new_msg = ChatMessage(user_id=user_id, role='user', content=user_text)
    db.session.add(new_msg)
    db.session.commit()
    
    # 2. Fetch Recent History (Last 10 messages) to give context
    # We order by ID desc to get newest, then reverse back to chronological order
    recent_history = ChatMessage.query.filter_by(user_id=user_id)\
        .order_by(ChatMessage.id.desc()).limit(10).all()
    recent_history.reverse()

    # 3. Build Prompt for Gemini
    chat_session = model.start_chat(history=[])
    
    # Pre-load the history into Gemini object
    history_payload = []
    for msg in recent_history:
        # Map our DB roles to Gemini roles ('user' -> 'user', 'model' -> 'model')
        history_payload.append({
            "role": "user" if msg.role == 'user' else "model",
            "parts": [msg.content]
        })

    # System instruction (Gemini Pro treats this as the first prompt often, or we wrap it)
    system_instruction = "You are the IsomoLink AI Tutor. Keep answers concise and helpful."

    try:
        # Create a chat object with history
        chat = model.start_chat(history=history_payload)
        
        # Send the new message
        response = chat.send_message(user_text + f"\n\n(System Note: {system_instruction})")
        ai_text = response.text
        
        # 4. Save AI Response to DB
        ai_msg = ChatMessage(user_id=user_id, role='model', content=ai_text)
        db.session.add(ai_msg)
        db.session.commit()
        
        # Convert to HTML for display
        html_response = markdown.markdown(ai_text)
        return jsonify({"response": html_response})
        
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({"response": "I'm having trouble connecting to the brain right now."})

# --- NEW ROUTE: LOAD HISTORY ---
@app.route('/api/chat/history', methods=['GET'])
def get_chat_history():
    if 'user_id' not in session: return jsonify([])
    
    # Get last 20 messages
    history = ChatMessage.query.filter_by(user_id=session['user_id'])\
        .order_by(ChatMessage.id.asc()).limit(20).all()
    
    return jsonify([{
        "role": msg.role,
        "content": markdown.markdown(msg.content) # Pre-format markdown for frontend
    } for msg in history])

# --- DB INIT (Run Once) ---
@app.route('/init-db')
def init_db():
    db.create_all()
    return "Database Tables Re-Created Successfully!"

if __name__ == '__main__':
    app.run(debug=True)
