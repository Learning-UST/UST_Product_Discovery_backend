import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_search():
    url = f"{BASE_URL}/search"
    payload = {
        "query": "Soup"
    }

    response = requests.post(url, json=payload)

    print("\n🔎 SEARCH RESPONSE")
    print("Status Code:", response.status_code)
    print(json.dumps(response.json(), indent=2))


def test_chat():
    url = f"{BASE_URL}/chat"
    payload = {
        "query": "Knorr Mexican Tomato Corn Soup nutritions?"
    }

    response = requests.post(url, json=payload)

    print("\n🤖 CHAT RESPONSE")
    print("Status Code:", response.status_code)
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    print("🚀 Running API Tests...\n")

    test_search()
    test_chat()

    print("\n✅ Tests completed.")