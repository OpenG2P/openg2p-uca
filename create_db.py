# create_db.py
import sqlite3

def create_programs_db():
    conn = sqlite3.connect('programs.db')
    cursor = conn.cursor()
    
    # Create the program_info table with a structured schema
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS program_info (
        program_id INTEGER PRIMARY KEY AUTOINCREMENT,
        program_name TEXT NOT NULL,
        description TEXT,
        eligibility_criteria TEXT,
        exclusions TEXT,
        application_procedure TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Sample data for the Kisan Samman Nidhi program
    sample_program = {
        'program_name': 'OpenG2P Kisan Samman Nidhi',
        'description': 'Financial assistance program for farmer families',
        'eligibility_criteria': 'All landholding farmers\' families, which have cultivable land holding in their names are eligible to get benefit under the scheme.',
        'exclusions': '''The following categories of beneficiaries of higher economic status shall not be eligible:
1. All Institutional Land holders.
2. Farmer families in which one or more of its members belong to following categories
3. Former and present holders of constitutional posts
4. Former and present Ministers/State Ministers and former/present Members of LokSabha/RajyaSabha
5. All serving or retired officers and employees of Central/State Government
6. All superannuated/retired pensioners whose monthly pension is Rs.10,000/-or more
7. All Persons who paid Income Tax in last assessment year
8. Professionals like Doctors, Engineers, Lawyers registered with Professional bodies''',
        'application_procedure': 'Visit the nearest government help centre.'
    }
    
    # Insert the sample program
    cursor.execute('''
    INSERT INTO program_info (
        program_name, description, eligibility_criteria, exclusions, application_procedure
    ) VALUES (?, ?, ?, ?, ?)
    ''', (
        sample_program['program_name'],
        sample_program['description'],
        sample_program['eligibility_criteria'],
        sample_program['exclusions'],
        sample_program['application_procedure']
    ))
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_programs_db()
