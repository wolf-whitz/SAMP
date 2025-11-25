import requests

url = "/detect"
data = {"text": "some test text"}
resp = requests.post(url, json=data)
print(resp.json())
