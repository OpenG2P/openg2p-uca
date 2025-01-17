import requests
import json

URL = 'http://13.202.113.132:8000/chat'
def send_query(url, query, thread_id):
    print('------')
    print(f'User query: {query}')
    print('------')
    myobj = {'query': query,
         'thread_id': thread_id}
    r = requests.post(url, json = myobj)
    rj = r.json()
    return (rj['ai_message'])

thread_id = 'user01_02'

query = 'Do you remember my name?'
print(send_query(URL, query, thread_id))
'''
query = 'Hi, Puneet here. How are you doing?' 
print(send_query(URL, query, thread_id))

query = 'Do you still remember my name?'
print(send_query(URL, query, thread_id))

query = 'How can I apply for OpenG2P vaccination program?' 
print(send_query(URL, query, thread_id))
'''
