print("APP START")
print("LINE_CHANNEL_SECRET =", bool(LINE_CHANNEL_SECRET))
print("LINE_CHANNEL_ACCESS_TOKEN =", bool(LINE_CHANNEL_ACCESS_TOKEN))
print("GEMINI_API_KEY =", bool(GEMINI_API_KEY))
print("SPREADSHEET_ID =", bool(SPREADSHEET_ID))
print("GOOGLE_CREDENTIALS =", bool(GOOGLE_CREDENTIALS))

import os
import json
import datetime

from flask import Flask, request, abort
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from google import genai

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
GOOGLE_CREDENTIALS = os.environ.get('GOOGLE_CREDENTIALS')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

client = genai.Client(api_key=GEMINI_API_KEY)

def get_sheets_service():
    creds_info = json.loads(GOOGLE_CREDENTIALS)

    creds = Credentials.from_service_account_info(
        creds_info,
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets'
        ]
    )

    return build(
        'sheets',
        'v4',
        credentials=creds
    )


def log_to_sheets(user_msg, bot_reply):
    try:
        service = get_sheets_service()

        now = datetime.datetime.now().strftime(
            '%Y-%m-%d %H:%M:%S'
        )

        values = [[
            now,
            user_msg,
            bot_reply
        ]]

        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range='工作表1!A:C',
            valueInputOption='RAW',
            body={'values': values}
        ).execute()

        print("已寫入 Google Sheet")

    except Exception as e:
        print(f"Sheets error: {e}")

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text
    
    # ================= 🧠 關鍵字判斷與專屬 Prompt 教學引導開始 =================
    
    # LINE 專屬排版指令（重複利用，確保 AI 嚴格遵守）
    line_style_instruction = """
⚠️ 【嚴格排版規則 - 專為 LINE 手機介面設計】：
1. 絕對禁止使用任何 Markdown 語法！不要輸出任何 `#`（井字號）、`*`（星號）、`-`（減號）或 `__`（底線）。
2. 請改用 Emoji（例如 📌, 🔹, ▪️, 📢）來當作條列式的開頭符號。
3. 大標題與小標題請直接用全形【】括號區隔，例如：【一、 颱風動態與氣象警報】。
4. 重點強調請直接用「引號」或【括號】包起來，禁止使用雙星號。
5. 段落與段落之間，請多空一行（換行），保持手機畫面的寬鬆與舒適度。
6. 嚴禁任何客套話（例如：好的，沒問題！以下是為您整理的...），請直接輸出筆記內容。
"""
    
    # 情況 1：使用者輸入以「/摘要」開頭
    if user_msg.startswith("/摘要"):
        pure_content = user_msg.replace("/摘要", "").strip()
        
        final_prompt = f"""你現在是一位專業的「長文速讀專家」。請為使用者提供的內容進行結構化摘要。

📌 【核心大綱】
(請用一句話總結這篇文章的核心宗旨)

📢 【三大關鍵重點】
🔹 (重點一)
🔹 (重點二)
🔹 (重點三)

🏃‍♂️ 【行動建議】
🔹 (如果有，請列出後續可以做的事情或啟發，若無則寫無)
{line_style_instruction}
以下是需要你摘要的內容：
{pure_content}"""

    # 情況 2：使用者輸入以「/待辦」開頭
    elif user_msg.startswith("/待辦"):
        pure_content = user_msg.replace("/待辦", "").strip()
        
        final_prompt = f"""你現在是一位「高效時間管理秘書」。請將使用者傳送的混亂日常瑣事或會議記錄，整理成乾淨的待辦清單。

📅 【待辦任務清單】
⬜️ (任務一)
⬜️ (任務二)

⚠️ 【時間或注意事項】
▪️ (請提取出提及的時間點、截止日或重要備註)
{line_style_instruction}
以下是使用者的零碎文字：
{pure_content}"""

    # 情況 3：使用者直接打「使用說明」
    elif user_msg.strip() == "使用說明":
        reply = "🤖 歡迎使用 AI 筆記秘書！\n\n你可以直接傳送文字讓我幫你梳理邏輯，也可以使用以下專屬功能：\n\n👉 輸入「/摘要 加上你的長文章」：自動啟動結構化重點濃縮。\n👉 輸入「/待辦 加上你的雜事」：自動生成精美 To-Do List。"

        log_to_sheets(user_msg, reply)
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
        return

    # 情況 4：使用者沒有輸入任何關鍵字（日常隨手筆記梳理）
    else:
        final_prompt = f"""你現在是個人的「知識管理秘書」。使用者的話通常是課堂隨手筆記或零碎思緒。
請幫他重新梳理邏輯，去除贅字，改成條列式、好閱讀的排版。
{line_style_instruction}
以下是使用者的隨手筆記：
{user_msg}"""

    # ================= 🧠 關鍵字判斷與專屬 Prompt 教學引導結束 =================

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=final_prompt
        )

        reply = response.text if response.text else "AI 沒有回傳內容"

        # 寫入 Google Sheet
        log_to_sheets(user_msg, reply)

    except Exception as e:
        print(f'Gemini error: {e}')
        reply = f'錯誤：{str(e)}'

        # 錯誤也記錄
        log_to_sheets(user_msg, reply)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    app.run()
