"""
MySQL Database Service for MediVault

Provides connection management using context managers to ensure proper
resource cleanup and transaction handling.
"""

import pymysql
from contextlib import contextmanager
from config import Config


class DatabaseService:
    """Wrapper for MySQL database operations with transaction support"""
    
    @staticmethod
    @contextmanager
    def get_connection():
        """
        Context manager for MySQL database connections.
        Yields an open connection that is automatically closed on exit.
        
        Example:
            with DatabaseService.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM medicines")
                results = cursor.fetchall()
        """
        connection = None
        try:
            connection = pymysql.connect(
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False  # Explicit transaction control
            )
            yield connection
        except pymysql.Error as e:
            if connection:
                connection.rollback()
            raise Exception(f"Database error: {str(e)}")
        finally:
            if connection:
                connection.close()

    @staticmethod
    def save_prescription(patient_id, doctor_id, s3_image_url, prescribed_date, medications, fhir_json=None):
        """
        Save prescription to database in a single transaction.
        
        Args:
            patient_id: Patient ID
            doctor_id: Doctor ID
            s3_image_url: URL of prescription image
            prescribed_date: Date of prescription (YYYY-MM-DD)
            medications: List of medication dicts with keys: name, dosage, frequency, duration
            fhir_json: Optional FHIR bundle JSON
        
        Returns:
            tuple: (prescription_id, medicines_count, error_message)
                - prescription_id: New prescription ID if successful, None on failure
                - medicines_count: Number of medicines saved
                - error_message: Error message if failed, None otherwise
        """
        with DatabaseService.get_connection() as conn:
            try:
                cursor = conn.cursor()
                
                # Step 1a: Insert prescription row
                insert_rx_sql = """
                    INSERT INTO prescriptions 
                    (patient_id, doctor_id, source, prescribed_date, s3_image_url, fhir_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """
                cursor.execute(insert_rx_sql, (
                    patient_id,
                    doctor_id,
                    'AI',
                    prescribed_date,
                    s3_image_url,
                    fhir_json
                ))
                prescription_id = cursor.lastrowid
                
                # Step 1b: Save medicines and links
                medicines_count = 0
                
                for med in medications:
                    med_name = med.get('name', '').strip()
                    if not med_name:
                        continue
                    
                    # Insert or ignore the medicine master record
                    insert_med_sql = "INSERT IGNORE INTO medicines (medicine_name) VALUES (%s)"
                    cursor.execute(insert_med_sql, (med_name,))
                    
                    # Get the medicine_id
                    select_med_sql = "SELECT medicine_id FROM medicines WHERE medicine_name = %s"
                    cursor.execute(select_med_sql, (med_name,))
                    med_result = cursor.fetchone()
                    
                    if med_result:
                        medicine_id = med_result['medicine_id']
                        
                        # Insert prescription_medicines link
                        insert_link_sql = """
                            INSERT INTO prescription_medicines 
                            (prescription_id, medicine_id, dosage, frequency, duration)
                            VALUES (%s, %s, %s, %s, %s)
                        """
                        cursor.execute(insert_link_sql, (
                            prescription_id,
                            medicine_id,
                            med.get('dosage', ''),
                            med.get('frequency', ''),
                            med.get('duration', '')
                        ))
                        medicines_count += 1
                
                # Commit the transaction
                conn.commit()
                
                return prescription_id, medicines_count, None
                
            except Exception as e:
                conn.rollback()
                error_msg = f"Failed to save prescription: {str(e)}"
                return None, 0, error_msg

    @staticmethod
    def update_prescription_fhir(prescription_id, fhir_json):
        """
        Update an existing prescription with FHIR bundle JSON.
        
        Args:
            prescription_id: Prescription ID to update
            fhir_json: FHIR bundle JSON
        
        Returns:
            tuple: (success, error_message)
        """
        with DatabaseService.get_connection() as conn:
            try:
                cursor = conn.cursor()
                
                update_sql = """
                    UPDATE prescriptions 
                    SET fhir_json = %s 
                    WHERE prescription_id = %s
                """
                cursor.execute(update_sql, (fhir_json, prescription_id))
                conn.commit()
                
                return True, None
                
            except Exception as e:
                conn.rollback()
                return False, f"Failed to update FHIR: {str(e)}"

    @staticmethod
    def check_db_connection():
        """Test database connectivity"""
        try:
            with DatabaseService.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True, "Database connection successful"
        except Exception as e:
            return False, f"Database connection failed: {str(e)}"
