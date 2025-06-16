import openai
import json
import requests
import time
import os # เพิ่มบรรทัดนี้

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

# --- ฟังก์ชันหลักของ Bridge Application ---
def run_assistant_bridge():
    print("\n--- Assistant Bridge Started ---")
    print("Type 'exit' to quit.\n")

    # สร้าง Thread ใหม่สำหรับการสนทนาแต่ละครั้ง (หรือใช้ Thread เดิมหากต้องการสนทนาต่อเนื่อง)
    thread = client.beta.threads.create()
    print(f"[Bridge] New Thread created: {thread.id}")

    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            print("Exiting Assistant Bridge.")
            break

        # 1. เพิ่มข้อความของผู้ใช้ลงใน Thread
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input,
        )

        # 2. สร้าง Run เพื่อให้ Assistant ประมวลผล
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
        )

        # 3. วนลูปตรวจสอบสถานะของ Run จนกว่าจะเสร็จสิ้นหรือต้องการการดำเนินการ
        while run.status == 'queued' or run.status == 'in_progress' or run.status == 'requires_action':
            time.sleep(1)  # รอ 1 วินาที ก่อนตรวจสอบสถานะอีกครั้ง
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
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
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )

        # 4. เมื่อ Run เสร็จสิ้น, ดึงข้อความทั้งหมดจาก Thread และแสดงข้อความล่าสุดของ Assistant
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(
                thread_id=thread.id
            )
            # แสดงข้อความล่าสุดของ Assistant
            for msg in reversed(messages.data):
                if msg.role == "assistant":
                    for content_block in msg.content:
                        if content_block.type == 'text':
                            print(f"Assistant: {content_block.text.value}")
                            break # แสดงแค่ข้อความแรกของ Assistant
                    break
        else:
            print(f"[Bridge] Run ended with status: {run.status}")

# --- รัน Bridge Application ---
if __name__ == "__main__":
    # ตัวอย่างการสร้าง Assistant และ Tool (ทำเพียงครั้งเดียว หรือถ้าคุณมีอยู่แล้วก็ข้ามไปได้)
    # หากคุณยังไม่มี Assistant ID ให้รันโค้ดนี้เพื่อสร้าง Assistant และ Tool
    # และคัดลอก ASSISTANT_ID ที่ได้ไปใส่ในโค้ดด้านบน
    # try:
    #     my_assistant = client.beta.assistants.retrieve(ASSISTANT_ID)
    #     print(f"[Bridge] Using existing Assistant: {my_assistant.id}")
    # except openai.NotFoundError:
    #     print("[Bridge] Assistant not found. Creating a new one...")
    #     my_assistant = client.beta.assistants.create(
    #         name="Order Bot",
    #         instructions="You are an order bot. Use the provided tools to submit orders.",
    #         model="gpt-4o", # หรือรุ่นที่คุณใช้
    #         tools=[
    #             {
    #                 "type": "function",
    #                 "function": {
    #                     "name": "submit_order",
    #                     "description": "Submits a customer order to the backend system.",
    #                     "parameters": {
    #                         "type": "object",
    #                         "properties": {
    #                             "menu": {"type": "string", "description": "Menu item ordered"},
    #                             "type": {"type": "string", "description": "Type of order (e.g., พร้อมทาน)"},
    #                             "quantity": {"type": "integer", "description": "Quantity of the item"},
    #                             "meat": {"type": "string", "description": "Type of meat"},
    #                             "nickname": {"type": "string", "description": "Customer\'s nickname"},
    #                             "phone": {"type": "string", "description": "Customer\'s phone number"},
    #                             "location": {"type": "string", "description": "Delivery location"},
    #                             "date": {"type": "string", "description": "Delivery date (YYYY-MM-DD)"},
    #                             "time": {"type": "string", "description": "Delivery time (HH:MM)"}
    #                         },
    #                         "required": ["menu", "type", "quantity", "meat", "nickname", "phone", "location", "date", "time"]
    #                     },
    #                 },
    #             }
    #         ]
    #     )
    #     ASSISTANT_ID = my_assistant.id
    #     print(f"[Bridge] New Assistant created with ID: {ASSISTANT_ID}")
    
    run_assistant_bridge()
