import os
from flask import Flask
from flask_bcrypt import Bcrypt
import mysql.connector

# Initialize security extensions
bcrypt = Bcrypt()

def create_app():
    """
    Application Factory to initialize and configure the Flask app,
    extensions, and modular blueprints using mysql.connector.
    """
    app = Flask(__name__)
    
    # Session and Security configurations
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key_for_clinic_appointment_system_99182')
    
    # XAMPP MySQL Default Configurations
    app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'localhost')
    app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
    app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '') # Default is empty in XAMPP
    app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'clinic_db')
    
    # Bind extensions
    bcrypt.init_app(app)
    
    # Safe Database Connection Helper using mysql.connector
    def get_db_connection():
        return mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB'],
            autocommit=True # Automatically commits transactions
        )
    
    app.get_db_connection = get_db_connection

    # Register blueprints (Routes)
    from app.routes.auth import auth_bp
    from app.routes.patient import patient_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp)
    
    return app