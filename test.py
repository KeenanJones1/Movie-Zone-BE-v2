import requests

BASE = 'http://127.0.0.1:5000/'
payload = {'uuid': '2345'}
response = requests.post(BASE + 'users', params=payload)

print(response.json())
