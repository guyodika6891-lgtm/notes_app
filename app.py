import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_bcrypt import Bcrypt
from models import db, User, Note, Tag
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-fallback-key-change-me')


app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///notes.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db.init_app(app)
bcrypt = Bcrypt(app)

with app.app_context():
    db.create_all()
    print("✅ Notes App database created successfully!")



def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    if not session.get('logged_in'):
        return render_template('index.html', notes=None)

    # Get user's notes: pinned first, then newest
    notes = Note.query.filter_by(user_id=session['user_id']).order_by(
        Note.pinned.desc(),
        Note.updated_at.desc()
    ).all()

    return render_template('index.html', notes=notes)


# Register Route
@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        username=request.form.get('username','').strip()
        email=request.form.get('email','').strip()
        password=request.form.get('password','').strip()
        confirm_password=request.form.get('confirm_password','').strip()

        errors=[]
        if not username or len(username)<3:
            errors.append('Username must be at least 3 characters')
        elif User.query.filter_by(username=username).first():
            errors.append('This username already registered,please enter other username')
        if not email or '@' not in email or '.' not in email:
            errors.append('Please Enter the Valid email')
        elif User.query.filter_by(email=email).first():
            errors.append('This Email are already Registered')
        if not password or len(password)<6:
            errors.append('Please enter Valid password')
        if password!=confirm_password:
            errors.append('Your password must be Matched')


        if errors:
            for error in errors:
                flash(error,'error')
            return render_template('register.html',username=username,email=email)


        hashed_password=bcrypt.generate_password_hash(password).decode('utf-8')
        new_user=User(username=username,email=email,password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registiration is successfully, please login','success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        username=request.form.get('username','').strip()
        password=request.form.get('password','').strip()

        user=User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash,password):
            session['user_id']=user.id
            session['username']=user.username
            session['logged_in']=True

            flash(f'well back,{username}!','success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/profile')
@login_required
def profile():
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out','info')
    return redirect(url_for('index'))

@app.route('/note/new', methods=['GET', 'POST'])
@login_required
def new_note():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        tags_input = request.form.get('tags', '').strip()

        if not content:
            flash('Content is required', 'error')
            return render_template('new_note.html', title=title, content=content, tags_input=tags_input)

        # Create note (OUTSIDE the if block)
        note = Note(
            title=title if title else None,
            content=content,
            user_id=session['user_id']
        )

        # Handle tags
        if tags_input:
            tag_names = [t.strip().lower() for t in tags_input.split(',') if t.strip()]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                note.tags.append(tag)

        db.session.add(note)
        db.session.commit()

        flash('Note created successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('new_note.html')


@app.route('/note/<int:note_id>')
@login_required
def view_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != session['user_id']:
        flash('You can only view your own notes.', 'error')
        return redirect(url_for('index'))
    return render_template('view_note.html', note=note)


@app.route('/note/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != session['user_id']:
        flash('You can only edit your own notes.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        tags_input = request.form.get('tags', '').strip()

        if not content:
            flash('Content is required', 'error')
            return render_template('edit_note.html', note=note)

        note.title = title if title else None
        note.content = content

        # Replace tags completely
        note.tags = []
        if tags_input:
            tag_names = [t.strip().lower() for t in tags_input.split(',') if t.strip()]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                note.tags.append(tag)

        db.session.commit()
        flash('Note updated successfully!', 'success')
        return redirect(url_for('view_note', note_id=note.id))

    return render_template('edit_note.html', note=note)


@app.route('/note/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != session['user_id']:
        flash('You can only delete your own notes.', 'error')
        return redirect(url_for('index'))

    db.session.delete(note)
    db.session.commit()

    flash('Note deleted successfully!', 'info')
    return redirect(url_for('index'))


@app.route('/note/<int:note_id>/toggle_pin')
@login_required
def toggle_pin(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != session['user_id']:
        flash('You can only modify your own notes.', 'error')
        return redirect(url_for('index'))

    note.pinned = not note.pinned
    db.session.commit()

    status = 'pinned' if note.pinned else 'unpinned'
    flash(f'Note {status}!', 'success')
    return redirect(url_for('index'))


@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    results = []

    if query:
        results = Note.query.filter(
            Note.user_id == session['user_id'],
            db.or_(
                Note.title.ilike(f'%{query}%'),
                Note.content.ilike(f'%{query}%')
            )
        ).order_by(Note.updated_at.desc()).all()

    return render_template('search.html', query=query, results=results)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500



if __name__ == '__main__':
    app.run(debug=True)