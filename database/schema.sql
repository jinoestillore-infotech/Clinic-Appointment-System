-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS clinic_db;
USE clinic_db;

-- 1. USERS TABLE (Unified table for credentials and authentication)
-- Roles: 'patient', 'staff', 'owner'
CREATE TABLE IF NOT EXISTS users (
id INT AUTO_INCREMENT PRIMARY KEY,
username VARCHAR(50) NOT NULL UNIQUE,
email VARCHAR(100) NOT NULL UNIQUE,
password_hash VARCHAR(255) NOT NULL,
role ENUM('patient', 'staff', 'owner') NOT NULL DEFAULT 'patient',
first_name VARCHAR(50) NOT NULL,
last_name VARCHAR(50) NOT NULL,
phone_number VARCHAR(15),
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. DOCTORS TABLE (Profile details linked to staff users or registered separately)
CREATE TABLE IF NOT EXISTS doctors (
id INT AUTO_INCREMENT PRIMARY KEY,
user_id INT UNIQUE, -- Links to the 'users' table if they have a login account
first_name VARCHAR(50) NOT NULL,
last_name VARCHAR(50) NOT NULL,
specialization VARCHAR(100) NOT NULL,
consultation_fee DECIMAL(10, 2) NOT NULL DEFAULT 500.00,
is_active TINYINT(1) DEFAULT 1,
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. APPOINTMENTS TABLE (The bridging schedule transaction table)
-- Statuses: 'Pending', 'Confirmed', 'Completed', 'Cancelled'
CREATE TABLE IF NOT EXISTS appointments (
id INT AUTO_INCREMENT PRIMARY KEY,
patient_id INT NOT NULL, -- Links to 'users' table (where role = 'patient')
doctor_id INT NOT NULL,
appointment_date DATE NOT NULL,
appointment_time TIME NOT NULL,
status ENUM('Pending', 'Confirmed', 'Completed', 'Cancelled') NOT NULL DEFAULT 'Pending',
symptoms_brief TEXT,
medical_notes TEXT,     -- Notes appended by doctor or staff post-appointment
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
UNIQUE KEY unique_booking (doctor_id, appointment_date, appointment_time) -- Double-booking protection constraint
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. BILLING TABLE (Tracks payment state and supplies Owner Dashboard metrics)
-- Statuses: 'Unpaid', 'Paid', 'Refunded'
CREATE TABLE IF NOT EXISTS billing (
id INT AUTO_INCREMENT PRIMARY KEY,
appointment_id INT NOT NULL UNIQUE,
amount_due DECIMAL(10, 2) NOT NULL,
payment_status ENUM('Unpaid', 'Paid', 'Refunded') NOT NULL DEFAULT 'Unpaid',
payment_method VARCHAR(50), -- e.g., 'Cash', 'G-Cash', 'Card'
billed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
paid_at TIMESTAMP NULL DEFAULT NULL,
FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert a default Owner account for bootstrapping (Password is 'owner123' hashed with bcrypt or similar, default mock insertion here)
-- Note: Make sure to hash this via Flask-Bcrypt later.
INSERT INTO users (username, email, password_hash, role, first_name, last_name, phone_number)
VALUES ('owner', 'owner@clinic.com', '$2b$12$e09121855a0f1225de02c0b467cb6df8bc4b66ff6d5f76bfe4e9a', 'owner', 'Clinic', 'Owner', '09171234567')
ON DUPLICATE KEY UPDATE username=username;