from flask import Blueprint, render_template, redirect, url_for, session, flash, current_app, request
from app import bcrypt

owner_bp = Blueprint('owner', __name__, url_prefix='/owner')

def owner_required(f):
    """
    Decorator to protect routes and ensure only logged-in system owners can access them.
    """
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'owner':
            flash('Access denied. Owner permissions required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@owner_bp.route('/dashboard')
@owner_required
def dashboard():
    """
    Lists all doctors in the clinic and provides management views.
    """
    connection = current_app.get_db_connection()
    doctors = []
    stats = {'total_doctors': 0, 'active_doctors': 0, 'total_users': 0}
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Fetch active and total doctors
        cursor.execute("SELECT * FROM doctors")
        doctors = cursor.fetchall()
        stats['total_doctors'] = len(doctors)
        stats['active_doctors'] = sum(1 for d in doctors if d['is_active'])
        
        # Fetch total system users count
        cursor.execute("SELECT COUNT(id) AS count FROM users")
        stats['total_users'] = cursor.fetchone()['count']
        
        cursor.close()
    except Exception as e:
        flash(f'An error occurred loading doctors details: {str(e)}', 'danger')
    finally:
        connection.close()
        
    return render_template('owner/dashboard.html', doctors=doctors, stats=stats)


@owner_bp.route('/doctors/add', methods=['POST'])
@owner_required
def add_doctor():
    """
    Creates a new doctor profile. This automatically generates a corresponding 
    user credential account with the 'staff' role so they can log in securely.
    """
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    phone = request.form.get('phone')
    specialization = request.form.get('specialization')
    fee = request.form.get('consultation_fee', 500.00)
    
    if not username or not email or not password or not first_name or not last_name or not specialization:
        flash('Please fill out all required doctor registration fields.', 'warning')
        return redirect(url_for('owner.dashboard'))
        
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    connection = current_app.get_db_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Verify no existing user conflicts
        cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
        if cursor.fetchone():
            flash('Username or Email is already registered in our database.', 'danger')
            cursor.close()
            return redirect(url_for('owner.dashboard'))
            
        # Create Staff User Account
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, first_name, last_name, phone_number)
            VALUES (%s, %s, %s, 'staff', %s, %s, %s)
        """, (username, email, hashed_password, first_name, last_name, phone))
        user_id = cursor.lastrowid
        
        # Link Doctor Profile
        cursor.execute("""
            INSERT INTO doctors (user_id, first_name, last_name, specialization, consultation_fee, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
        """, (user_id, first_name, last_name, specialization, fee))
        
        flash(f'Successfully added Dr. {first_name} {last_name} to CareSync medical roster!', 'success')
        cursor.close()
    except Exception as e:
        flash(f'Failed to add doctor record: {str(e)}', 'danger')
    finally:
        connection.close()
        
    return redirect(url_for('owner.dashboard'))


@owner_bp.route('/doctors/edit/<int:doctor_id>', methods=['POST'])
@owner_required
def edit_doctor(doctor_id):
    """
    Allows the owner to edit any detail about the doctor, including consultation fees,
    specializations, profile status, and names.
    """
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    specialization = request.form.get('specialization')
    fee = request.form.get('consultation_fee')
    is_active = request.form.get('is_active', type=int)
    
    if not first_name or not last_name or not specialization or not fee:
        flash('All doctor modification fields are required.', 'warning')
        return redirect(url_for('owner.dashboard'))
        
    connection = current_app.get_db_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get doctor user_id to keep names aligned
        cursor.execute("SELECT user_id FROM doctors WHERE id = %s", (doctor_id,))
        doctor_record = cursor.fetchone()
        
        if doctor_record:
            user_id = doctor_record['user_id']
            # Synchronize names to parent User Table
            cursor.execute("""
                UPDATE users SET first_name = %s, last_name = %s WHERE id = %s
            """, (first_name, last_name, user_id))
            
            # Update Doctor Profile Info
            cursor.execute("""
                UPDATE doctors 
                SET first_name = %s, last_name = %s, specialization = %s, consultation_fee = %s, is_active = %s
                WHERE id = %s
            """, (first_name, last_name, specialization, fee, is_active, doctor_id))
            
            flash('Doctor settings updated successfully!', 'success')
        else:
            flash('Doctor profile not found.', 'danger')
            
        cursor.close()
    except Exception as e:
        flash(f'Failed to update clinician: {str(e)}', 'danger')
    finally:
        connection.close()
        
    return redirect(url_for('owner.dashboard'))


@owner_bp.route('/users')
@owner_required
def users():
    """
    Displays user administration directory containing roles, status tracking,
    and access governance parameters.
    """
    connection = current_app.get_db_connection()
    user_records = []
    try:
        cursor = connection.cursor(dictionary=True)
        # Fetch all users except the currently logged-in Owner
        cursor.execute("SELECT id, username, email, role, first_name, last_name, status, created_at FROM users WHERE id != %s", (session['user_id'],))
        user_records = cursor.fetchall()
        cursor.close()
    except Exception as e:
        flash(f'Could not load user data: {str(e)}', 'danger')
    finally:
        connection.close()
        
    return render_template('owner/users.html', users=user_records)


@owner_bp.route('/users/status/<int:target_id>', methods=['POST'])
@owner_required
def update_user_status(target_id):
    """
    Allows the owner to suspend, block, or reactivate any user account.
    """
    new_status = request.form.get('status')
    if new_status not in ('active', 'suspended', 'blocked'):
        flash('Invalid status modification parameters specified.', 'danger')
        return redirect(url_for('owner.users'))
        
    connection = current_app.get_db_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, target_id))
        flash(f'User access status updated to "{new_status.capitalize()}"', 'info')
        cursor.close()
    except Exception as e:
        flash(f'Could not adjust user status: {str(e)}', 'danger')
    finally:
        connection.close()
        
    return redirect(url_for('owner.users'))


@owner_bp.route('/users/delete/<int:target_id>', methods=['POST'])
@owner_required
def delete_user(target_id):
    """
    Permanently deletes a user from the CareSync system. Parent/Child constraints
    will be handled automatically by ON DELETE CASCADE table properties.
    """
    connection = current_app.get_db_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("DELETE FROM users WHERE id = %s", (target_id,))
        flash('User account permanently deleted from records database.', 'success')
        cursor.close()
    except Exception as e:
        flash(f'Failed to execute deletion operation: {str(e)}', 'danger')
    finally:
        connection.close()
        
    return redirect(url_for('owner.users'))