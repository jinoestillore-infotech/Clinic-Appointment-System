from flask import Blueprint, render_template, redirect, url_for, session, flash, current_app, request

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

def staff_required(f):
    """
    Decorator to protect routes and ensure only logged-in clinical staff can access them.
    """
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'staff':
            flash('Access restricted. Please log in with a Staff/Doctor account.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@staff_bp.route('/dashboard')
@staff_required
def dashboard():
    """
    Renders the clinician dashboard containing stats and active/past consultations.
    """
    connection = current_app.get_db_connection()
    appointments = []
    stats = {'total': 0, 'Pending': 0, 'Confirmed': 0, 'Completed': 0, 'Cancelled': 0}
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, specialization FROM doctors WHERE user_id = %s", (session['user_id'],))
        doctor = cursor.fetchone()
        
        if doctor:
            doctor_id = doctor['id']
            cursor.execute("""
                SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.symptoms_brief, a.medical_notes,
                       u.first_name AS pat_first, u.last_name AS pat_last, u.phone_number,
                       b.amount_due, b.payment_status
                FROM appointments a
                JOIN users u ON a.patient_id = u.id
                LEFT JOIN billing b ON a.id = b.appointment_id
                WHERE a.doctor_id = %s
                ORDER BY a.appointment_date DESC, a.appointment_time ASC
            """, (doctor_id,))
            appointments = cursor.fetchall()
            
            for appt in appointments:
                stats['total'] += 1
                status = appt['status']
                if status in stats:
                    stats[status] += 1
        else:
            flash('Doctor profile not found.', 'warning')
        cursor.close()
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'danger')
    finally:
        connection.close()
        
    return render_template('staff/dashboard.html', appointments=appointments, stats=stats)


@staff_bp.route('/pending')
@staff_required
def pending():
    """
    Renders the isolated pending appointments queue for clinical staff.
    """
    connection = current_app.get_db_connection()
    appointments = []
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id FROM doctors WHERE user_id = %s", (session['user_id'],))
        doctor = cursor.fetchone()
        
        if doctor:
            doctor_id = doctor['id']
            cursor.execute("""
                SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.symptoms_brief,
                       u.first_name AS pat_first, u.last_name AS pat_last, u.phone_number,
                       b.amount_due, b.payment_status
                FROM appointments a
                JOIN users u ON a.patient_id = u.id
                LEFT JOIN billing b ON a.id = b.appointment_id
                WHERE a.doctor_id = %s AND a.status = 'Pending'
                ORDER BY a.appointment_date ASC, a.appointment_time ASC
            """, (doctor_id,))
            appointments = cursor.fetchall()
        cursor.close()
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'danger')
    finally:
        connection.close()
        
    return render_template('staff/pending.html', appointments=appointments)


@staff_bp.route('/confirm/<int:appointment_id>', methods=['POST'])
@staff_required
def confirm(appointment_id):
    """
    Confirms a patient's pending appointment.
    """
    connection = current_app.get_db_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("UPDATE appointments SET status = 'Confirmed' WHERE id = %s", (appointment_id,))
        flash('Appointment schedule successfully confirmed.', 'success')
        cursor.close()
    except Exception as e:
        flash(f'Failed to update appointment: {str(e)}', 'danger')
    finally:
        connection.close()
        
    # Support smart redirection back to pending queue if submitted from there
    if request.form.get('redirect_to') == 'pending':
        return redirect(url_for('staff.pending'))
    return redirect(url_for('staff.dashboard'))


@staff_bp.route('/cancel/<int:appointment_id>', methods=['POST'])
@staff_required
def cancel(appointment_id):
    """
    Cancels or declines an appointment.
    """
    connection = current_app.get_db_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("UPDATE appointments SET status = 'Cancelled' WHERE id = %s", (appointment_id,))
        flash('Appointment has been marked as Cancelled.', 'info')
        cursor.close()
    except Exception as e:
        flash(f'Failed to cancel appointment: {str(e)}', 'danger')
    finally:
        connection.close()
        
    if request.form.get('redirect_to') == 'pending':
        return redirect(url_for('staff.pending'))
    return redirect(url_for('staff.dashboard'))


@staff_bp.route('/complete/<int:appointment_id>', methods=['POST'])
@staff_required
def complete(appointment_id):
    """
    Completes a consultation and updates records.
    """
    medical_notes = request.form.get('medical_notes')
    connection = current_app.get_db_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            UPDATE appointments 
            SET status = 'Completed', medical_notes = %s 
            WHERE id = %s
        """, (medical_notes, appointment_id))
        cursor.execute("""
            UPDATE billing 
            SET payment_status = 'Paid', payment_method = 'Cash', paid_at = CURRENT_TIMESTAMP 
            WHERE appointment_id = %s
        """, (appointment_id,))
        flash('Consultation completed successfully.', 'success')
        cursor.close()
    except Exception as e:
        flash(f'Failed to complete consultation: {str(e)}', 'danger')
    finally:
        connection.close()
        
    return redirect(url_for('staff.dashboard'))