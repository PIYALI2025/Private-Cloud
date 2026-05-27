import requests
import sqlite3

# Let's read the last registered Alice user and get her token
conn = sqlite3.connect("cloud_vault.db")
cursor = conn.cursor()
cursor.execute("SELECT id, username, hashed_password FROM users WHERE username LIKE 'alice_%' ORDER BY id DESC LIMIT 1")
user = cursor.fetchone()
conn.close()

if not user:
    print("No Alice user found.")
    exit(1)

alice_id, username, password = user
print(f"Alice: id={alice_id}, username={username}")

# Let's login
BASE_URL = "http://127.0.0.1:8000"
res = requests.post(f"{BASE_URL}/auth/login", data={"username": username, "password": "securepassword123"})
if res.status_code != 200:
    print(f"Login failed: {res.text}")
    exit(1)

token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Call notifications
res_notify = requests.get(f"{BASE_URL}/notifications", headers=headers)
print("Status Code:", res_notify.status_code)
print("Notifications Response:", res_notify.json())
