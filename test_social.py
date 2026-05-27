import requests
import uuid
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_social_test():
    print("Starting Social Vault & Collaboration E2E Test...")
    
    # 1. Setup Random Users
    user_a = f"alice_{uuid.uuid4().hex[:6]}"
    user_b = f"bob_{uuid.uuid4().hex[:6]}"
    password = "securepassword123"

    print(f"[*] Registering User A (Alice): {user_a}")
    res = requests.post(f"{BASE_URL}/auth/signup", json={"username": user_a, "password": password})
    assert res.status_code == 200, f"Failed to register user A: {res.text}"
    
    print(f"[*] Registering User B (Bob): {user_b}")
    res = requests.post(f"{BASE_URL}/auth/signup", json={"username": user_b, "password": password})
    assert res.status_code == 200, f"Failed to register user B: {res.text}"

    # 2. Login
    print("[*] Logging in both users")
    res_a = requests.post(f"{BASE_URL}/auth/login", data={"username": user_a, "password": password})
    assert res_a.status_code == 200
    token_a = res_a.json()["access_token"]
    
    res_b = requests.post(f"{BASE_URL}/auth/login", data={"username": user_b, "password": password})
    assert res_b.status_code == 200
    token_b = res_b.json()["access_token"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. User Discovery (Bob searches for Alice)
    print(f"[*] User B (Bob) searching for User A (Alice): '{user_a[:5]}'")
    res_search = requests.get(f"{BASE_URL}/users/search?q={user_a[:5]}", headers=headers_b)
    assert res_search.status_code == 200
    search_results = res_search.json()
    alice_user = next(u for u in search_results if u["username"] == user_a)
    alice_id = alice_user["id"]
    print(f"[+] Found {user_a} successfully! ID: {alice_id}")

    # 4. User A (Alice) Uploads File
    print("[*] User A (Alice) uploading file")
    files = {"file": ("shared_vault_doc.txt", b"Secret social collaboration vault content!", "text/plain")}
    res_upload = requests.post(f"{BASE_URL}/upload", files=files, headers=headers_a)
    assert res_upload.status_code == 200, f"Upload failed: {res_upload.text}"
    share_slug = res_upload.json()["share_slug"]

    # 5. User B (Bob) Requests Access via the new endpoint
    request_msg = "Hello Alice, please let me see the vault document!"
    print(f"[*] User B (Bob) requesting access via POST /access/request for file 'shared_vault_doc.txt'")
    res_req = requests.post(f"{BASE_URL}/access/request", json={
        "owner_id": alice_id,
        "filename": "shared_vault_doc.txt",
        "message": request_msg
    }, headers=headers_b)
    assert res_req.status_code == 200, f"Request failed: {res_req.text}"
    request_id = res_req.json()["id"]

    # Verify B can't download yet
    print("[*] Verifying User B (Bob) is blocked pending approval")
    res_dl_blocked = requests.get(f"{BASE_URL}/download/{share_slug}", headers=headers_b)
    assert res_dl_blocked.status_code == 403, f"Expected 403, got {res_dl_blocked.status_code}"

    # 6. User A (Alice) checks notification list
    print("[*] User A (Alice) checking notifications")
    res_notify = requests.get(f"{BASE_URL}/notifications", headers=headers_a)
    assert res_notify.status_code == 200
    notifications = res_notify.json()
    assert len(notifications) > 0, "No notifications found for User A"
    assert notifications[0]["request_id"] == request_id
    assert notifications[0]["requester_username"] == user_b
    assert notifications[0]["file_name"] == "shared_vault_doc.txt"
    assert notifications[0]["message"] == request_msg
    notification_id = notifications[0]["id"]
    print(f"[+] Notification matches: {notifications[0]}")

    # 7. User A (Alice) Approves Access via PATCH /access/respond/{request_id}
    print(f"[*] User A (Alice) approving request {request_id}")
    res_approve = requests.patch(f"{BASE_URL}/access/respond/{request_id}", json={"response": "approved"}, headers=headers_a)
    assert res_approve.status_code == 200, f"Approval failed: {res_approve.text}"

    # Verify notification is cleared
    res_notify_after = requests.get(f"{BASE_URL}/notifications", headers=headers_a)
    assert len(res_notify_after.json()) == 0, "Notification was not marked read/cleared"

    # 8. User B (Bob) checks Shared Files list
    print("[*] User B (Bob) checking shared files workspace")
    res_shared = requests.get(f"{BASE_URL}/files/shared", headers=headers_b)
    assert res_shared.status_code == 200
    shared_files = res_shared.json()
    assert len(shared_files) > 0, "No shared files found for User B"
    assert shared_files[0]["filename"] == "shared_vault_doc.txt"
    assert shared_files[0]["share_slug"] == share_slug
    print(f"[+] Shared files matches: {shared_files[0]}")

    # 9. User B downloads the file successfully
    print("[*] User B (Bob) downloading shared file")
    res_dl_success = requests.get(f"{BASE_URL}/download/{share_slug}", headers=headers_b)
    assert res_dl_success.status_code == 200, f"Download failed: {res_dl_success.text}"
    assert res_dl_success.text == "Secret social collaboration vault content!"
    print("[+] Download content matched successfully!")

    print("\n[SUCCESS] All Social Vault & Collaboration smoke tests passed!")

if __name__ == "__main__":
    try:
        run_social_test()
    except AssertionError as e:
        print(f"\n[FAIL] Test Failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        sys.exit(1)
