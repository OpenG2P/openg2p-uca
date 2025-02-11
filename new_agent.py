# new_agent.py (or you can rename it to main.py)

from lib_for_sql import process_query

def main():
    print('==== Ask about government programs (or type "quit" to exit)')
    
    while True:
        query = input()
        
        if query.lower() == 'quit':
            break
            
        response = process_query(query)
        if response:
            print("================================== AI Message ==================================")
            print(response.content)
        else:
            print("Error processing query. Please try again.")

if __name__ == "__main__":
    main()
