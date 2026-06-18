from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from app import bcrypt

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles Patient registration and securely hashes passwords into MySQL.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        
        # Basic validation
        if not username or not email or not password or not first_name or not last_name:
            flash('Please fill out all required fields.', 'danger')
            return render_template('auth/register.html')
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        connection = current_app.get_db_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Check if username or email already exists
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            existing_user = cursor.fetchone()
            
            if existing_user:
                flash('Username or Email already registered!', 'warning')
                cursor.close()
                return render_template('auth/register.html')
            
            # Insert the new patient (Active by default)
            sql = """
                INSERT INTO users (username, email, password_hash, role, first_name, last_name, phone_number, status)
                VALUES (%s, %s, %s, 'patient', %s, %s, %s, 'active')
            """
            cursor.execute(sql, (username, email, hashed_password, first_name, last_name, phone))
            cursor.close()
                
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
        finally:
            connection.close()

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Verifies user credentials, checks authorization status (active, suspended, blocked),
    and establishes a role-based session.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        connection = current_app.get_db_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            
            if user and bcrypt.check_password_hash(user['password_hash'], password):
                # GOVERNANCE CHECK: Block entry if user status is suspended or blocked
                if user['status'] == 'suspended':
                    flash('Your account access has been temporarily suspended. Please contact clinic administration.', 'warning')
                    return render_template('auth/login.html')
                elif user['status'] == 'blocked':
                    flash('Login refused. This account has been permanently blocked.', 'danger')
                    return render_template('auth/login.html')
                
                # Save user metadata in session
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['first_name'] = user['first_name']
                
                flash(f"Welcome back, {user['first_name']}!", 'success')
                
                # Role-based redirection pathing
                if user['role'] == 'owner':
                    return redirect(url_for('owner.dashboard'))
                elif user['role'] == 'staff':
                    return redirect(url_for('staff.dashboard'))
                else:
                    return redirect(url_for('patient.dashboard'))
            else:
                flash('Invalid username or password.', 'danger')
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
        finally:
            connection.close()

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """
    Clears the system session and redirects to login.
    """
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))