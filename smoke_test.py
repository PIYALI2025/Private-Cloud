import requests
import uuid
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_test():
    print("Starting E2E Smoke Test...")
    
    # 1. Setup Random Users
    user_a = f"alice_{uuid.uuid4().hex[:6]}"
    user_b = f"bob_{uuid.uuid4().hex[:6]}"
    password = "securepassword123"

    print(f"[*] Registering User A: {user_a}")
    res = requests.post(f"{BASE_URL}/auth/signup", json={"username": user_a, "password": password})
    assert res.status_code == 200, f"Failed to register user A: {res.text}"
    
    print(f"[*] Registering User B: {user_b}")
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

    # 3. User A Uploads File
    print("[*] User A uploading file")
    files = {"file": ("test_smoke.txt", b"Hello from the smoke test file!", "text/plain")}
    res_upload = requests.post(f"{BASE_URL}/upload", files=files, headers=headers_a)
    assert res_upload.status_code == 200, f"Upload failed: {res_upload.text}"
    share_slug = res_upload.json()["share_slug"]

    # 4. User B Requests Access
    print(f"[*] User B requesting access via slug: {share_slug}")
    res_req = requests.post(f"{BASE_URL}/files/{share_slug}/request", headers=headers_b)
    assert res_req.status_code == 200, f"Request failed: {res_req.text}"

    # Verify B can't download yet
    print("[*] Verifying User B is blocked pending approval")
    res_dl_blocked = requests.get(f"{BASE_URL}/download/{share_slug}", headers=headers_b)
    assert res_dl_blocked.status_code == 403, f"Expected 403, got {res_dl_blocked.status_code}"

    # 5. User A Approves Access
    print("[*] User A checking pending requests")
    res_pending = requests.get(f"{BASE_URL}/requests/pending", headers=headers_a)
    assert res_pending.status_code == 200
    requests_list = res_pending.json()
    assert len(requests_list) > 0
    request_id = requests_list[0]["request_id"]

    print(f"[*] User A approving request {request_id}")
    res_approve = requests.patch(f"{BASE_URL}/requests/{request_id}/approve", headers=headers_a)
    assert res_approve.status_code == 200

    # 6. User B Downloads Successfully
    print("[*] User B attempting download again")
    res_dl_success = requests.get(f"{BASE_URL}/download/{share_slug}", headers=headers_b)
    assert res_dl_success.status_code == 200, f"Download failed: {res_dl_success.text}"
    assert res_dl_success.text == "Hello from the smoke test file!"

    print("\n[SUCCESS] All smoke tests passed successfully!")

if __name__ == "__main__":
    try:
        run_test()
    except AssertionError as e:
        print(f"\n[FAIL] Test Failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        sys.exit(1)
