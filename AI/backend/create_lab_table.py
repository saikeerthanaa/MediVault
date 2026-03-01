#!/usr/bin/env python3
"""Create lab_reports table in MySQL database"""

import pymysql
from config import Config

try:
    conn = pymysql.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )
    cursor = conn.cursor()
    
    # Create lab_reports table
    sql = """
    CREATE TABLE IF NOT EXISTS lab_reports (
        id INT AUTO_INCREMENT PRIMARY KEY,
        patient_id INT NOT NULL,
        test_date DATE NOT NULL,
        lab_name VARCHAR(255),
        report_type ENUM('Blood', 'Urine', 'Thyroid', 'Lipid', 'Liver', 'Kidney', 'Imaging', 'Other') NOT NULL,
        s3_image_url VARCHAR(500),
        ocr_text LONGTEXT,
        lab_values_json LONGTEXT,
        extracted_conditions JSON,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_patient_id (patient_id),
        INDEX idx_test_date (test_date),
        INDEX idx_report_type (report_type)
    )
    """
    
    cursor.execute(sql)
    conn.commit()
    print("✓ lab_reports table created successfully")
    
    # Verify it was created
    cursor.execute("SHOW TABLES")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"✓ Tables in database: {tables}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
