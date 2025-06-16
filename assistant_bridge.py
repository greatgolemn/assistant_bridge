import openai
import json
import requests
import time
import os
from flask import Flask, request, jsonify # เพิ่ม Flask

app = Flask(__name__)

# --- กำหนดค่าของคุณที่นี่ (อ่านจาก Environment Variables) ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_APPS_SCRIPT_WEB_APP_URL = os.environ.get("GOOGLE_APPS_SCRIPT_WEB_APP_URL")
ASSISTANT_ID = os.environ.get("ASSISTANT_ID")

# ตรวจสอบว่า Environment Variables ถูกตั้งค่าหรือไม่
if not OPENAI_API_KEY or not GOOGLE_APPS_SCRIPT_WEB_APP_URL or not ASSISTANT_ID:
    print("Error: Missing one or more required environment variables.")
    print("Please set OPENAI_API_KEY, GOOGLE_APPS_SCRIPT_WEB_APP_URL, and ASSISTANT_ID.")
    exit(1)

# --- ตั้งค่า OpenAI Client ---
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# --- ฟังก์ชันสำหรับเรียก Google Apps Script Web App ---
def call_google_apps_script(function_name, arguments):
    if function_name == "submit_order":
        print(f"[Bridge] Calling Google Apps Script for submit_order with arguments: {arguments}")
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(GOOGLE_APPS_SCRIPT_WEB_APP_URL, data=json.dumps(arguments), headers=headers)
            response.raise_for_status()  # ตรวจสอบว่ามีข้อผิดพลาด HTTP หรือไม่
            result = response.json()
            print(f"[Bridge] Google Apps Script response: {result}")
            return result
        except requests.exceptions.RequestException as e:
            print(f"[Bridge] Error calling Google Apps Script: {e}")
            return {"success": False, "error": str(e)}
    else:
        return {"success": False, "error": f"Unknown function: {function_name}"}

# --- Endpoint สำหรับรับข้อความจากภายนอก ---
@app.route("/message", methods=["POST"])
def handle_message():
    data = request.json
    user_message = data.get("message")
    thread_id = data.get("thread_id") # หากต้องการใช้ Thread เดิม

    if not user_message:
        return jsonify({"error": "'message' field is required"}), 400

    # หากไม่มี thread_id ให้สร้างใหม่ (หรือจัดการตามที่คุณต้องการ)
    if not thread_id:
        thread = client.beta.threads.create()
        thread_id = thread.id
        print(f"[Bridge] New Thread created: {thread_id}")
    else:
        print(f"[Bridge] Using existing Thread: {thread_id}")

    try:
        # 1. เพิ่มข้อความของผู้ใช้ลงใน Thread
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_message,
        )

        # 2. สร้าง Run เพื่อให้ Assistant ประมวลผล
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
        )

        # 3. วนลูปตรวจสอบสถานะของ Run จนกว่าจะเสร็จสิ้นหรือต้องการการดำเนินการ
        while run.status == 'queued' or run.status == 'in_progress' or run.status == 'requires_action':
            time.sleep(1)  # รอ 1 วินาที ก่อนตรวจสอบสถานะอีกครั้ง
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

            if run.status == 'requires_action':
                print("[Bridge] Assistant requires action (Tool Call).")
                tool_outputs = []
                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)

                    # เรียกใช้ฟังก์ชันจริงตามที่ Assistant แนะนำ
                    output = call_google_apps_script(function_name, arguments)

                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(output) # ผลลัพธ์ต้องเป็น string
                    })
                
                # ส่งผลลัพธ์ของ Tool กลับไปให้ Assistant
                run = client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )

        # 4. เมื่อ Run เสร็จสิ้น, ดึงข้อความทั้งหมดจาก Thread และส่งข้อความล่าสุดของ Assistant กลับไป
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(
                thread_id=thread_id
            )
            assistant_response = ""
            for msg in reversed(messages.data):
                if msg.role == "assistant":
                    for content_block in msg.content:
                        if content_block.type == 'text':
                            assistant_response = content_block.text.value
                            break
                    break
            return jsonify({"response": assistant_response, "thread_id": thread_id})
        else:
            return jsonify({"error": f"Run ended with status: {run.status}"}), 500

    except Exception as e:
        print(f"[Bridge] An error occurred: {e}")
        return jsonify({"error": str(e)}), 500

# --- รัน Flask App ---
# if __name__ == "__main__":
    # Render จะใช้ Gunicorn ในการรัน Flask App ใน Production
    # สำหรับการทดสอบบน Local สามารถรันแบบนี้ได้
