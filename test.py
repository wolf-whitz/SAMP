import requests

url = "https://throat-residents-handhelds-member.trycloudflare.com/detect"
data = {"text": "some test text"}
resp = requests.post(url, json=data)
print(resp.json())
