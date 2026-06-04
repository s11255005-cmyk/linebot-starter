import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from google import genai

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

client = genai.Client(api_key=GEMINI_API_KEY)

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
    
    # 情況 1：使用者輸入以「/摘要」開頭
    if user_msg.startswith("/摘要"):
        # 去除指令文字，只留下要摘要的內文
        pure_content = user_msg.replace("/摘要", "").strip()
        
        # 這是你精心設計的教學引導 A
        final_prompt = f"""你現在是一位專業的「長文速讀專家」。請為使用者提供的內容進行結構化摘要。
嚴格遵守以下格式輸出，不要包含任何多餘的客套話：

📌 【核心大綱】
(請用一句話總結這篇文章的核心宗旨)

💡 【三大關鍵重點】
1. (重點一)
2. (重點二)
3. (重點三)

🏃‍♂️ 【行動建議】
- (如果有，請列出後續可以做的事情或啟發，若無則寫無)

以下是需要你摘要的內容：
{pure_content}"""

    # 情況 2：使用者輸入以「/待辦」開頭
    elif user_msg.startswith("/待辦"):
        pure_content = user_msg.replace("/待辦", "").strip()
        
        # 這是你精心設計的教學引導 B
        final_prompt = f"""你現在是一位「高效時間管理秘書」。請將使用者傳送的混亂日常瑣事或會議記錄，整理成乾淨的待辦清單。
必須遵守以下格式，且禁止說客套話：

📅 【待辦任務清單】
⬜️ (任務一)
⬜️ (任務二)

⚠️ 【時間或注意事項】
- (請提取出提及的時間點、截止日或重要備註)

以下是使用者的零碎文字：
{pure_content}"""

    # 情況 3：使用者直接打「使用說明」
    elif user_msg.strip() == "使用說明":
        # 這種情況不需要問 Gemini，Python 直接給答案，省 Token 又秒回！
        reply = "🤖 歡迎使用 AI 筆記秘書！\n\n你可以直接傳送文字讓我幫你梳理邏輯，也可以使用以下專屬功能：\n\n👉 輸入「/摘要 加上你的長文章」：自動啟動結構化重點濃縮。\n👉 輸入「/待辦 加上你的雜事」：自動生成精美 To-Do List。"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
        return  # 直接結束這個 function，不走下面的 Gemini 流程

    # 情況 4：使用者沒有輸入任何關鍵字（走日常筆記梳理的預設引導）
    else:
        # 即使沒有關鍵字，我們也不用 AI 的預設回答，而是用我們設計的筆記風格引導它
        final_prompt = f"""你現在是個人的「知識管理秘書」。使用者的話通常是零碎的思緒或隨手筆記。
請幫他重新梳理邏輯，去除贅字，改成條列式、好閱讀的 Markdown 筆記格式。
必須保持語氣專業、排版精美，不要有「好的，沒問題」等聊天罐頭訊息。

以下是使用者的隨手筆記：
{user_msg}"""

    # ================= 🧠 關鍵字判斷與專屬 Prompt 教學引導結束 =================

    try:
        # 將我們組裝好、帶有「教學引導」的 final_prompt 送給 Gemini
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=final_prompt
        )
        reply = response.text
    except Exception as e:
        print(f'Gemini error: {e}')
        reply = f'錯誤：{str(e)}'
        
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    app.run()
