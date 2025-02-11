import sqlite3
import pandas as pd

def create_pdb():
    # Create database connection
    conn = sqlite3.connect('pdb')
    cursor = conn.cursor()
    
    # Create table with schema
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pinfo (
        pid INTEGER PRIMARY KEY AUTOINCREMENT,
        mneumonic TEXT NOT NULL,
        description TEXT,
        domain TEXT,
        eligibility TEXT
    )
    ''')
    
    # Read CSV file - note the quoting parameters for proper handling of nested quotes
    df = pd.read_csv('Data/data.csv', quoting=1)  # QUOTE_ALL=1
    
    # Rename sql_query column to eligibility
    df = df.rename(columns={'sql_query': 'eligibility'})
    
    # Insert data from CSV
    for _, row in df.iterrows():
        cursor.execute('''
        INSERT INTO pinfo (mneumonic, description, domain, eligibility)
        VALUES (?, ?, ?, ?)
        ''', (
            row['mneumonic'],
            row['description'],
            row['domain'],
            row['eligibility']
        ))
    
    # Commit and close
    conn.commit()
    conn.close()
    print("Database created successfully!")

if __name__ == "__main__":
    try:
        create_pdb()
    except Exception as e:
        print(f"Error: {e}")
