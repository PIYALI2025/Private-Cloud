import requests
import uuid
import sys
import io

BASE_URL = "http://127.0.0.1:8000"

def run_test():
    print("Starting Preview & Profile Photo E2E Test...")
    
    # 1. Setup Random User
    username = f"user_{uuid.uuid4().hex[:6]}"
    password = "securepassword123"

    print(f"[*] Registering User: {username}")
    res = requests.post(f"{BASE_URL}/auth/signup", json={"username": username, "password": password})
    assert res.status_code == 200, f"Registration failed: {res.text}"
    
    print("[*] Logging in user")
    res_login = requests.post(f"{BASE_URL}/auth/login", data={"username": username, "password": password})
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload Profile Photo
    print("[*] Uploading Profile Photo")
    photo_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82" # 1x1 empty PNG
    files = {"file": ("avatar.png", photo_data, "image/png")}
    res_photo = requests.post(f"{BASE_URL}/user/profile-photo", files=files, headers=headers)
    assert res_photo.status_code == 200, f"Profile upload failed: {res_photo.text}"
    photo_filename = res_photo.json()["profile_photo"]
    print(f"[+] Profile photo uploaded: {photo_filename}")

    # 3. Retrieve Profile Photo
    print(f"[*] Getting profile photo for: {username}")
    res_get_photo = requests.get(f"{BASE_URL}/user/profile-photo/{username}")
    assert res_get_photo.status_code == 200
    assert res_get_photo.content == photo_data
    print("[+] Profile photo retrieved matches uploaded binary exactly!")

    # 4. Check Current User endpoint
    print("[*] Getting current user profile info from /user/me")
    res_me = requests.get(f"{BASE_URL}/user/me", headers=headers)
    assert res_me.status_code == 200
    user_data = res_me.json()
    assert user_data["username"] == username
    assert user_data["profile_photo"] == photo_filename
    print(f"[+] /user/me matched successfully: {user_data}")

    # 5. Upload File
    print("[*] Uploading text document for preview check")
    files_doc = {"file": ("readme.txt", b"Antigravity Cloud Storage System", "text/plain")}
    res_upload = requests.post(f"{BASE_URL}/upload", files=files_doc, headers=headers)
    assert res_upload.status_code == 200
    slug = res_upload.json()["share_slug"]

    # 6. Verify Inline Preview works with Token in Query Parameter
    print(f"[*] Accessing GET /preview/{slug}?token={token}")
    res_preview = requests.get(f"{BASE_URL}/preview/{slug}?token={token}")
    assert res_preview.status_code == 200, f"Preview failed: {res_preview.text}"
    assert res_preview.text == "Antigravity Cloud Storage System"
    assert "content-disposition" not in res_preview.headers or "attachment" not in res_preview.headers["content-disposition"]
    print("[+] File preview returned matching content inline successfully!")

    print("\n[SUCCESS] All Preview & Profile Photo smoke tests passed!")

if __name__ == "__main__":
    try:
        run_test()
    except AssertionError as e:
        print(f"\n[FAIL] Test Failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        sys.exit(1)
