import requests

url = "http://127.0.0.1:8000/detect"
data = {"text": "f2ck niggers im so gay", "threshold": 0.72, "block": []}

response = requests.post(url, json=data)
print(response.json())
