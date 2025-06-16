import requests
import json

# แทนที่ด้วย Web app URL ที่คุณได้จาก Google Apps Script
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbxAXgZYl462YmmJN0W1KobousevH8mm647wdSm3JTL0EUJyyATfhaOT53uFVNGayOuOZQ/exec"

# ข้อมูลตัวอย่างที่จะส่ง
data_to_send = {
    "menu": "ไม่เอาหนังหมู - เผ็ดปกติ",
    "type": "พร้อมทาน",
    "quantity": 2,
    "meat": "หมู",
    "nickname": "เจน",
    "phone": "022222222",
    "location": "สันทราย",
    "date": "16-10-2023",
    "time": "16:00"
}

headers = {'Content-Type': 'application/json'}

try:
    response = requests.post(WEB_APP_URL, data=json.dumps(data_to_send), headers=headers)
    response.raise_for_status()  # ตรวจสอบว่ามีข้อผิดพลาด HTTP หรือไม่
    print("Response from Web App:", response.json())
    if response.json().get("success"):
        print("Data sent successfully!")
    else:
        print("Failed to send data.")
except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")

