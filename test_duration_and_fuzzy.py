import requests
import uuid
import sys
import sqlite3
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:8000"

def run_custom_tests():
    print("Starting Custom E2E Enhancements Verification...")
    
    # 1. Setup Random Users
    user_a = f"alice_{uuid.uuid4().hex[:6]}"
    user_b = f"bob_{uuid.uuid4().hex[:6]}"
    password = "securepassword123"

    print(f"[*] Registering User A (Alice): {user_a}")
    res = requests.post(f"{BASE_URL}/auth/signup", json={"username": user_a, "password": password})
    assert res.status_code == 200
    token_a = res.json()["access_token"]
    
    print(f"[*] Registering User B (Bob): {user_b}")
    res = requests.post(f"{BASE_URL}/auth/signup", json={"username": user_b, "password": password})
    assert res.status_code == 200
    token_b = res.json()["access_token"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Retrieve User A ID for Bob's search
    res_search = requests.get(f"{BASE_URL}/users/search?q={user_a}", headers=headers_b)
    alice_id = res_search.json()[0]["id"]

    # 2. Upload duplicate filename files for Alice
    print("[*] Alice uploads 'report.pdf' and 'report.txt'")
    files_pdf = {"file": ("report.pdf", b"PDF Report Content", "application/pdf")}
    res_pdf = requests.post(f"{BASE_URL}/upload", files=files_pdf, headers=headers_a)
    assert res_pdf.status_code == 200
    slug_pdf = res_pdf.json()["share_slug"]

    files_txt = {"file": ("report.txt", b"TXT Report Content", "text/plain")}
    res_txt = requests.post(f"{BASE_URL}/upload", files=files_txt, headers=headers_a)
    assert res_txt.status_code == 200
    slug_txt = res_txt.json()["share_slug"]

    # 3. Test Fuzzy Lookup & Selection on duplicate choices
    print("[*] Bob requests access to 'report' (without extension)")
    res_req = requests.post(f"{BASE_URL}/access/request", json={
        "owner_id": alice_id,
        "filename": "report",
        "message": "Give me report please!",
        "duration": "7days"
    }, headers=headers_b)
    assert res_req.status_code == 200
    outcome = res_req.json()
    assert outcome.get("status") == "multiple_choices", f"Expected multiple choices, got: {outcome}"
    choices = outcome["choices"]
    assert len(choices) == 2, f"Expected 2 choices, got: {len(choices)}"
    print("[+] Multiple Choices identified successfully!")
    for c in choices:
        print(f"    - Choice: ID={c['id']}, Filename={c['filename']}, Type={c['file_type']}")

    # Bob selects the PDF report to request access
    selected_choice = next(c for c in choices if c["filename"] == "report.pdf")
    pdf_file_id = selected_choice["id"]
    print(f"[*] Bob requests access to exact PDF file ID {pdf_file_id} ('report.pdf')")
    res_req_exact = requests.post(f"{BASE_URL}/access/request", json={
        "owner_id": alice_id,
        "filename": "report",
        "message": "Give me PDF report please!",
        "duration": "1day",
        "file_id": pdf_file_id
    }, headers=headers_b)
    assert res_req_exact.status_code == 200
    req_json = res_req_exact.json()
    assert req_json["file_id"] == pdf_file_id
    request_id_pdf = req_json["id"]
    print("[+] Access request created successfully with selected file ID!")

    # 4. Test Timed Access Expiration
    print("[*] Alice approves PDF request")
    res_app = requests.patch(f"{BASE_URL}/access/respond/{request_id_pdf}", json={"response": "approved"}, headers=headers_a)
    assert res_app.status_code == 200

    print("[*] Verifying Bob can download report.pdf initially")
    res_dl = requests.get(f"{BASE_URL}/download/{slug_pdf}", headers=headers_b)
    assert res_dl.status_code == 200
    assert res_dl.text == "PDF Report Content"
    print("[+] Access is currently active.")

    # Manually expire the collaborator record in the SQLite database to simulate timed expiration
    print("[*] Simulating timed access expiration in the database...")
    conn = sqlite3.connect("cloud_vault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (user_b,))
    bob_db_id = cursor.fetchone()[0]
    print(f"    - Bob's database ID: {bob_db_id}")
    past_time = (datetime.utcnow() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S.%f")
    cursor.execute("UPDATE collaborators SET expires_at = ? WHERE file_id = ? AND user_id = ?", (past_time, pdf_file_id, bob_db_id))
    cursor.execute("SELECT id, expires_at, duration FROM collaborators WHERE file_id = ?", (pdf_file_id,))
    collabs = cursor.fetchall()
    print(f"    - Updated database collaborator records: {collabs}")
    conn.commit()
    conn.close()

    print("[*] Bob attempts to download report.pdf again after expiration")
    res_dl_expired = requests.get(f"{BASE_URL}/download/{slug_pdf}", headers=headers_b)
    assert res_dl_expired.status_code == 403, f"Expected 403 Forbidden, got: {res_dl_expired.status_code}"
    print("[+] Dynamic download access blocked due to expired permissions!")

    # Check if collaborator permission record was automatically removed
    conn = sqlite3.connect("cloud_vault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM collaborators WHERE file_id = ?", (pdf_file_id,))
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 0, f"Expected collaborator record to be auto-deleted, but got count: {count}"
    print("[+] Expired permission was automatically pruned from the database!")

    # 5. Test Deny Notification Flow
    print("[*] Bob requests access to report.txt")
    res_req_txt = requests.post(f"{BASE_URL}/access/request", json={
        "owner_id": alice_id,
        "filename": "report.txt",
        "message": "Let me see txt please!",
        "duration": "forever"
    }, headers=headers_b)
    assert res_req_txt.status_code == 200
    request_id_txt = res_req_txt.json()["id"]

    print("[*] Alice denies access to report.txt")
    res_deny = requests.patch(f"{BASE_URL}/access/respond/{request_id_txt}", json={"response": "deny"}, headers=headers_a)
    assert res_deny.status_code == 200

    print("[*] Bob checks notifications for a denial alert")
    res_notify_b = requests.get(f"{BASE_URL}/notifications", headers=headers_b)
    assert res_notify_b.status_code == 200
    notifs_b = res_notify_b.json()
    assert len(notifs_b) > 0, "Expected at least 1 notification"
    deny_notif = next(n for n in notifs_b if n["notification_type"] == "request_denied")
    assert f"denied your request" in deny_notif["message"]
    print(f"[+] Deny notification verified: {deny_notif['message']}")

    # Bob dismisses the notification
    notif_id = deny_notif["id"]
    print(f"[*] Bob clears/dismisses notification ID {notif_id}")
    res_clear = requests.patch(f"{BASE_URL}/notifications/{notif_id}/read", headers=headers_b)
    assert res_clear.status_code == 200

    # Verify notifications list is empty for Bob
    res_notify_after = requests.get(f"{BASE_URL}/notifications", headers=headers_b)
    assert len(res_notify_after.json()) == 0
    print("[+] Notification successfully dismissed and inbox is clear!")

    print("\n[SUCCESS] All custom E2E enhancement tests passed successfully!")

if __name__ == "__main__":
    try:
        run_custom_tests()
    except AssertionError as e:
        print(f"\n[FAIL] Test Assertion Failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        sys.exit(1)
