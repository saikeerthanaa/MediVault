-- MediVault Lab Reports Table Migration
-- Create lab_reports table for storing lab test reports

CREATE TABLE IF NOT EXISTS lab_reports (
    id INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT NOT NULL,
    test_date DATE NOT NULL,
    lab_name VARCHAR(255),
    report_type ENUM('Blood', 'Urine', 'Thyroid', 'Lipid', 'Liver', 'Kidney', 'Imaging', 'Other') NOT NULL,
    s3_image_url VARCHAR(500),
    ocr_text LONGTEXT,
    lab_values_json LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    extracted_conditions JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES prescriptions(patient_id) ON DELETE CASCADE,
    INDEX idx_lab_patient (patient_id),
    INDEX idx_lab_test_date (test_date),
    INDEX idx_lab_type (report_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
