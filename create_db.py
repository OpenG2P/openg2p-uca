import sqlite3
import pandas as pd

def create_program_db():
    """
    Creates a SQLite database 'program_db' with table 'program_info'
    containing program eligibility criteria and related information.
    """
    # Create database connection
    conn = sqlite3.connect('program_db')
    cursor = conn.cursor()
    
    # Create table with schema
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS program_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mneumonic TEXT NOT NULL,
        description TEXT,
        domain TEXT,
        sql_query TEXT
    )
    ''')
    
    try:
        # Read CSV file with proper handling of nested quotes and line endings
        df = pd.read_csv('Data/g2p_eligibility_rule_definition_Sheet1.1.csv', 
                        quoting=1,  # QUOTE_ALL=1
                        escapechar='\\',
                        encoding='utf-8')
        
        # Insert data from CSV
        for _, row in df.iterrows():
            cursor.execute('''
            INSERT INTO program_info (mneumonic, description, domain, sql_query)
            VALUES (?, ?, ?, ?)
            ''', (
                row['mneumonic'],
                row['description'],
                row['domain'],
                row['sql_query']
            ))
        
        # Commit changes
        conn.commit()
        print("Database created successfully!")
        
        # Verify data
        cursor.execute("SELECT COUNT(*) FROM program_info")
        count = cursor.fetchone()[0]
        print(f"Total records inserted: {count}")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    
    finally:
        # Close connection
        conn.close()

if __name__ == "__main__":
    create_program_db()
