from flask import Blueprint, render_template, redirect, url_for, session, flash, current_app, request
from datetime import datetime

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

def login_required(f):
    """
    Decorator to ensure routes are protected and only accessible to logged-in patients.
    """
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'patient':
            flash('Please log in as a patient to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def auto_cancel_expired_appointments(cursor):
    """
    Database sweep helper: Automatically transitions unconfirmed pending appointments
    to 'Cancelled' if their scheduled date and time are in the past.
    """
    cursor.execute("""
        UPDATE appointments 
        SET status = 'Cancelled' 
        WHERE status = 'Pending' 
          AND (appointment_date < CURDATE() 
               OR (appointment_date = CURDATE() AND appointment_time < CURTIME()))
    """)


@patient_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Fetches and displays active and past appointments with their corresponding billing information.
    Runs the auto-cancellation sweep beforehand.
    """
    connection = current_app.get_db_connection()
    upcoming_appointments = []
    past_appointments = []
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Run database sweep to cancel past-due pending appointments
        auto_cancel_expired_appointments(cursor)
        
        # Fetch upcoming appointments (Pending, Confirmed)
        cursor.execute("""
            SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.symptoms_brief,
                   d.first_name AS doc_first, d.last_name AS doc_last, d.specialization,
                   b.amount_due, b.payment_status
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            LEFT JOIN billing b ON a.id = b.appointment_id
            WHERE a.patient_id = %s AND a.status IN ('Pending', 'Confirmed')
            ORDER BY a.appointment_date ASC, a.appointment_time ASC
        """, (session['user_id'],))
        upcoming_appointments = cursor.fetchall()
        
        # Fetch past consultations (Completed, Cancelled)
        cursor.execute("""
            SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.medical_notes, a.doctor_id,
                   d.first_name AS doc_first, d.last_name AS doc_last, d.specialization,
                   b.amount_due, b.payment_status
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            LEFT JOIN billing b ON a.id = b.appointment_id
            WHERE a.patient_id = %s AND a.status IN ('Completed', 'Cancelled')
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
        """, (session['user_id'],))
        past_appointments = cursor.fetchall()
        
        cursor.close()
    except Exception as e:
        flash(f'System encountered an error loading dashboard: {str(e)}', 'danger')
    finally:
        connection.close()
        
    return render_template('patient/dashboard.html', upcoming=upcoming_appointments, past=past_appointments)


@patient_bp.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    """
    Displays the appointment booking sheet and handles reservation submission.
    Includes validation logic to prevent double-booking.
    """
    connection = current_app.get_db_connection()
    doctors = []
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Clean up database on load
        auto_cancel_expired_appointments(cursor)
        
        cursor.execute("SELECT id, first_name, last_name, specialization, consultation_fee FROM doctors WHERE is_active = 1")
        doctors = cursor.fetchall()
        cursor.close()
    except Exception as e:
        flash(f'Unable to load available specialists: {str(e)}', 'danger')

    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        date_str = request.form.get('appointment_date')
        time_str = request.form.get('appointment_time')
        symptoms = request.form.get('symptoms')
        
        if not doctor_id or not date_str or not time_str:
            flash('Please complete all required schedule selections.', 'warning')
            connection.close()
            return render_template('patient/book.html', doctors=doctors)
            
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Double-booking guardrail
            cursor.execute("""
                SELECT id FROM appointments 
                WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s AND status != 'Cancelled'
            """, (doctor_id, date_str, time_str))
            double_booked = cursor.fetchone()
            
            if double_booked:
                flash('The selected time slot has already been reserved. Please choose a different hour.', 'warning')
                cursor.close()
                connection.close()
                return render_template('patient/book.html', doctors=doctors)
            
            # Insert the appointment record
            cursor.execute("""
                INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, status, symptoms_brief)
                VALUES (%s, %s, %s, %s, 'Pending', %s)
            """, (session['user_id'], doctor_id, date_str, time_str, symptoms))
            appointment_id = cursor.lastrowid
            
            cursor.execute("SELECT consultation_fee FROM doctors WHERE id = %s", (doctor_id,))
            doctor_info = cursor.fetchone()
            fee = doctor_info['consultation_fee'] if doctor_info else 500.00
            
            # Insert billing entry
            cursor.execute("""
                INSERT INTO billing (appointment_id, amount_due, payment_status)
                VALUES (%s, %s, 'Unpaid')
            """, (appointment_id, fee))
            
            cursor.close()
            flash('Your appointment schedule request has been submitted!', 'success')
            return redirect(url_for('patient.dashboard'))
            
        except Exception as e:
            flash(f'Failed to schedule appointment: {str(e)}', 'danger')
        finally:
            connection.close()
            
    if connection.is_connected():
        connection.close()
        
    return render_template('patient/book.html', doctors=doctors)


@patient_bp.route('/cancel/<int:appointment_id>', methods=['POST'])
@login_required
def cancel(appointment_id):
    """
    Allows patients to securely and permanently delete their own upcoming appointments.
    Deletes child billing records first to avoid foreign key failures.
    """
    connection = current_app.get_db_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT status FROM appointments WHERE id = %s AND patient_id = %s", (appointment_id, session['user_id']))
        appt = cursor.fetchone()
        
        if not appt:
            flash('Appointment details not found.', 'danger')
        elif appt['status'] in ('Completed', 'Cancelled'):
            flash('Completed or cancelled appointments cannot be modified.', 'warning')
        else:
            # Completely delete billing and appointment logs to satisfy auto-delete logic
            cursor.execute("DELETE FROM billing WHERE appointment_id = %s", (appointment_id,))
            cursor.execute("DELETE FROM appointments WHERE id = %s AND patient_id = %s", (appointment_id, session['user_id']))
            flash('Your appointment schedule reservation has been removed.', 'info')
            
        cursor.close()
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'danger')
    finally:
        connection.close()
        
    return redirect(url_for('patient.dashboard'))