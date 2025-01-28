import requests
import json

URL = 'http://13.202.113.132:8000/chat'
def send_query(url, query, thread_id):
    print('=================================== User Message==========================')
    print(f'{query}')
    myobj = {'query': query,
         'thread_id': thread_id}
    r = requests.post(url, json = myobj)
    rj = r.json()
    return (rj['ai_message'])

thread_id = 'user01_10'

query = 'Hi, how are you doing?'
print(send_query(URL, query, thread_id))

query = 'Does OpenG2P offer any benefit programs? Total how many programs are afvailable?'
print(send_query(URL, query, thread_id))

query = 'How do I apply for the vaccination program?'
print(send_query(URL, query, thread_id))

