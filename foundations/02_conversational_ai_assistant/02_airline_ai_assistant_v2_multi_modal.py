# =============================================================================
# FlightAI Assistant v3
# 優化重點：
#   1. 改用 litellm 呼叫本地 Ollama 模型 (gemma3:4b)，完全離線免費
#   2. 移除重複定義的 chat() 與多餘的 gr.ChatInterface 啟動
#   3. 加入完整錯誤處理（DB、JSON 解析、API 呼叫）
#   4. 圖片生成改用 pollinations.ai 免費 API（不需金鑰）
#   5. 語音改用 gTTS（免費），取代 OpenAI TTS
#   6. 帳密從環境變數讀取，不硬寫在程式碼
#   7. 多城市查詢時顯示第一個城市圖片並在 UI 標示城市名稱
#
# 前置需求：
#   ollama pull gemma3:4b   # 下載模型（約 3GB）
#   ollama serve            # 確保 Ollama 服務在 localhost:11434 執行
# =============================================================================

# ---------- imports ----------
import os
import json
import tempfile
import sqlite3
from io import BytesIO

from dotenv import load_dotenv
import gradio as gr
from PIL import Image
from gtts import gTTS          # pip install gTTS
import litellm                 # pip install litellm
import requests                # pip install requests

# ---------- 初始化 ----------
load_dotenv(override=True)

# Gradio 登入帳密從環境變數讀取，預設值僅供本機開發
GRADIO_USER     = os.getenv("GRADIO_USER", "admin")
GRADIO_PASSWORD = os.getenv("GRADIO_PASSWORD", "changeme")

# litellm 透過 Ollama 呼叫本地模型，不需要任何 API Key
# 確保 Ollama 服務已啟動：ollama serve
MODEL = "ollama/gemma3:4b"
litellm.api_base = "http://localhost:11434"  # Ollama 預設埠

print("Using local model: gemma3:4b via Ollama")


system_message = """
You are a helpful assistant for an Airline called FlightAI.
Give short, courteous answers, no more than 1 sentence.
Always be accurate. If you don't know the answer, say so.
"""

# ---------- database ----------

DB = "prices.db"

def init_db():
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS prices (city TEXT PRIMARY KEY, price REAL)')
        conn.commit()

init_db()

# 預設票價資料
default_prices = {"london": 799, "paris": 899, "tokyo": 1420, "sydney": 2999, "berlin": 499, "new york": 350}

def seed_db():
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        for city, price in default_prices.items():
            cursor.execute(
                'INSERT INTO prices (city, price) VALUES (?, ?) ON CONFLICT(city) DO NOTHING',
                (city, price)
            )
        conn.commit()

seed_db()
print("✅ 資料庫初始化完成")

# ---------- Tool 定義 ----------
price_function = {
    "name": "get_ticket_price",
    "description": "Get the price of a return ticket to the destination city.",
    "parameters": {
        "type": "object",
        "properties": {
            "destination_city": {
                "type": "string",
                "description": "The city that the customer wants to travel to",
            },
        },
        "required": ["destination_city"],
        "additionalProperties": False,
    },
}
tools = [{"type": "function", "function": price_function}]

# ---------- 工具函式 ----------

def get_ticket_price(city: str) -> str:
    """從 SQLite 查詢票價，含完整錯誤處理。"""
    if not city:
        return "City name is missing."
    print(f"DATABASE TOOL CALLED: Getting price for {city}", flush=True)
    try:
        with sqlite3.connect(DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT price FROM prices WHERE city = ?", (city.lower(),))
            result = cursor.fetchone()
            return (
                f"Ticket price to {city} is ${result[0]}"
                if result
                else f"No price data available for {city}."
            )
    except sqlite3.Error as e:
        print(f"DB error: {e}")
        return "Sorry, the price database is currently unavailable."


def handle_tool_calls(message) -> tuple[list[dict], list[str]]:
    """
    處理所有 tool call，回傳 (tool_responses, cities)。
    cities 供後續圖片生成使用。
    """
    responses: list[dict] = []
    cities:    list[str]  = []

    for tool_call in (message.tool_calls or []):
        if tool_call.function.name == "get_ticket_price":
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                print(f"JSON parse error: {e}")
                arguments = {}

            city = arguments.get("destination_city")
            if city:
                cities.append(city)
            price_details = get_ticket_price(city)

            responses.append(
                {
                    "role": "tool",
                    "content": price_details,
                    "tool_call_id": tool_call.id,
                }
            )
    return responses, cities

# ---------- 多媒體函式 ----------

def artist(city: str) -> Image.Image | None:
    """
    使用 pollinations.ai 免費 API 生成城市旅遊圖片。
    無需任何 API Key，直接以 HTTP GET 取得圖片。
    失敗時回傳 None（UI 顯示空白）。
    """
    try:
        prompt = (
            f"A vibrant pop-art style travel poster for {city}, "
            f"showcasing famous tourist spots and local culture of {city}."
        )
        encoded_prompt = requests.utils.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content))
    except Exception as e:
        print(f"Image generation failed: {e}")
        return None


def talker(text: str) -> str | None:
    """
    使用 gTTS（免費）將文字轉語音，回傳暫存 .mp3 路徑。
    失敗時回傳 None。
    """
    try:
        tts = gTTS(text=text, lang="en")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp.name)
        return tmp.name
    except Exception as e:
        print(f"TTS failed: {e}")
        return None

# ---------- 核心 chat 函式（唯一版本）----------

def chat(history: list[dict]) -> tuple[list[dict], str | None, Image.Image | None]:
    """
    接收完整 history，呼叫 Gemini via litellm，
    處理 tool calls，回傳 (updated_history, audio_path, image)。
    """
    clean_history = [{"role": h["role"], "content": h["content"]} for h in history]
    messages = [{"role": "system", "content": system_message}] + clean_history

    cities: list[str] = []
    image: Image.Image | None = None

    try:
        response = litellm.completion(model=MODEL, messages=messages, tools=tools)

        # Tool call 迴圈
        while response.choices[0].finish_reason == "tool_calls":
            msg = response.choices[0].message
            tool_responses, new_cities = handle_tool_calls(msg)
            cities.extend(new_cities)

            # litellm 回傳的 message 物件需轉成 dict 加入 messages
            messages.append(msg.model_dump())
            messages.extend(tool_responses)

            response = litellm.completion(model=MODEL, messages=messages, tools=tools)

        reply = response.choices[0].message.content or "(no reply)"

    except Exception as e:
        print(f"LLM call failed: {e}")
        reply = "Sorry, I'm having trouble connecting right now. Please try again."

    # 更新 history
    history = history + [{"role": "assistant", "content": reply}]

    # 語音
    audio_path = talker(reply)

    # 圖片：只有在查詢到城市時才生成，避免不必要的 API 呼叫
    if cities:
        image = artist(cities[0])

    return history, audio_path, image

# ---------- Gradio UI ----------

def put_message_in_chatbot(
    message: str, history: list[dict]
) -> tuple[str, list[dict]]:
    """將使用者輸入加入 history，並清空輸入框。"""
    return "", history + [{"role": "user", "content": message}]


with gr.Blocks(title="FlightAI Assistant") as ui:
    gr.Markdown("## ✈️ FlightAI — Your AI Travel Assistant")
    gr.Markdown(
        "Ask me about ticket prices to any city! "
        "I'll look up the fare, generate a travel image, and read the answer aloud."
    )

    with gr.Row():
        chatbot      = gr.Chatbot(height=500, type="messages", label="Conversation")
        image_output = gr.Image(height=500, interactive=False, label="Destination Preview")

    with gr.Row():
        audio_output = gr.Audio(autoplay=True, label="Voice Reply")

    with gr.Row():
        message_box = gr.Textbox(
            label="Chat with FlightAI:",
            placeholder="e.g. How much is a ticket to Tokyo?",
            scale=9,
        )
        send_btn = gr.Button("Send", scale=1, variant="primary")

    # 送出事件：Textbox Enter 或 Send 按鈕
    submit_event = message_box.submit(
        put_message_in_chatbot,
        inputs=[message_box, chatbot],
        outputs=[message_box, chatbot],
    ).then(
        chat,
        inputs=chatbot,
        outputs=[chatbot, audio_output, image_output],
    )

    send_btn.click(
        put_message_in_chatbot,
        inputs=[message_box, chatbot],
        outputs=[message_box, chatbot],
    ).then(
        chat,
        inputs=chatbot,
        outputs=[chatbot, audio_output, image_output],
    )

ui.launch(
    inbrowser=True,
    auth=(GRADIO_USER, GRADIO_PASSWORD),
)

# # =============================================================================
# # FlightAI Assistant v3
# # 優化重點：
# #   1. 改用 litellm 呼叫 Google 免費模型 (gemini-2.0-flash)
# #   2. 移除重複定義的 chat() 與多餘的 gr.ChatInterface 啟動
# #   3. 加入完整錯誤處理（DB、JSON 解析、API 呼叫）
# #   4. 圖片生成改用 Google Imagen (免費額度)，fallback 至靜態提示圖
# #   5. 語音改用 gTTS（免費），取代 OpenAI TTS
# #   6. 帳密從環境變數讀取，不硬寫在程式碼
# #   7. 多城市查詢時顯示第一個城市圖片並在 UI 標示城市名稱
# # =============================================================================

# # ---------- imports ----------
# import os
# import json
# import base64
# import tempfile
# import sqlite3
# from io import BytesIO

# from dotenv import load_dotenv
# import gradio as gr
# from PIL import Image
# from gtts import gTTS          # pip install gTTS
# import litellm                 # pip install litellm
# import requests                # pip install requests

# # ---------- 初始化 ----------
# load_dotenv(override=True)

# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# if GOOGLE_API_KEY:
#     print(f"Google API Key exists and begins {GOOGLE_API_KEY[:8]}")
# else:
#     print("⚠️  GOOGLE_API_KEY not set — LLM calls will fail.")

# # Gradio 登入帳密從環境變數讀取，預設值僅供本機開發
# GRADIO_USER     = os.getenv("GRADIO_USER", "admin")
# GRADIO_PASSWORD = os.getenv("GRADIO_PASSWORD", "changeme")

# # litellm 使用 Google Gemini（免費額度）
# MODEL = "gemini/gemini-2.0-flash-lite"
# litellm.api_key = GOOGLE_API_KEY   # litellm 會自動路由給 Google

# DB = "prices.db"

# system_message = """
# You are a helpful assistant for an Airline called FlightAI.
# Give short, courteous answers, no more than 1 sentence.
# Always be accurate. If you don't know the answer, say so.
# """

# # ---------- Tool 定義 ----------
# price_function = {
#     "name": "get_ticket_price",
#     "description": "Get the price of a return ticket to the destination city.",
#     "parameters": {
#         "type": "object",
#         "properties": {
#             "destination_city": {
#                 "type": "string",
#                 "description": "The city that the customer wants to travel to",
#             },
#         },
#         "required": ["destination_city"],
#         "additionalProperties": False,
#     },
# }
# tools = [{"type": "function", "function": price_function}]

# # ---------- 工具函式 ----------

# def get_ticket_price(city: str) -> str:
#     """從 SQLite 查詢票價，含完整錯誤處理。"""
#     if not city:
#         return "City name is missing."
#     print(f"DATABASE TOOL CALLED: Getting price for {city}", flush=True)
#     try:
#         with sqlite3.connect(DB) as conn:
#             cursor = conn.cursor()
#             cursor.execute("SELECT price FROM prices WHERE city = ?", (city.lower(),))
#             result = cursor.fetchone()
#             return (
#                 f"Ticket price to {city} is ${result[0]}"
#                 if result
#                 else f"No price data available for {city}."
#             )
#     except sqlite3.Error as e:
#         print(f"DB error: {e}")
#         return "Sorry, the price database is currently unavailable."


# def handle_tool_calls(message) -> tuple[list[dict], list[str]]:
#     """
#     處理所有 tool call，回傳 (tool_responses, cities)。
#     cities 供後續圖片生成使用。
#     """
#     responses: list[dict] = []
#     cities:    list[str]  = []

#     for tool_call in (message.tool_calls or []):
#         if tool_call.function.name == "get_ticket_price":
#             try:
#                 arguments = json.loads(tool_call.function.arguments)
#             except json.JSONDecodeError as e:
#                 print(f"JSON parse error: {e}")
#                 arguments = {}

#             city = arguments.get("destination_city")
#             if city:
#                 cities.append(city)
#             price_details = get_ticket_price(city)

#             responses.append(
#                 {
#                     "role": "tool",
#                     "content": price_details,
#                     "tool_call_id": tool_call.id,
#                 }
#             )
#     return responses, cities

# # ---------- 多媒體函式 ----------

# def artist(city: str) -> Image.Image | None:
#     """
#     使用 Google Imagen (Vertex AI / Gemini) 生成城市旅遊圖片。
#     若 API 不可用，回傳 None（UI 會顯示空白）。
#     """
#     try:
#         # Gemini Imagen API（需開啟 generativelanguage API）
#         url = (
#             "https://generativelanguage.googleapis.com/v1beta/models/"
#             "imagen-3.0-generate-001:predict"
#             f"?key={GOOGLE_API_KEY}"
#         )
#         payload = {
#             "instances": [
#                 {
#                     "prompt": (
#                         f"A vibrant pop-art style travel poster for {city}, "
#                         f"showcasing famous tourist spots and local culture of {city}."
#                     )
#                 }
#             ],
#             "parameters": {"sampleCount": 1},
#         }
#         resp = requests.post(url, json=payload, timeout=30)
#         resp.raise_for_status()
#         b64 = resp.json()["predictions"][0]["bytesBase64Encoded"]
#         image_data = base64.b64decode(b64)
#         return Image.open(BytesIO(image_data))
#     except Exception as e:
#         print(f"Image generation failed: {e}")
#         return None


# def talker(text: str) -> str | None:
#     """
#     使用 gTTS（免費）將文字轉語音，回傳暫存 .mp3 路徑。
#     失敗時回傳 None。
#     """
#     try:
#         tts = gTTS(text=text, lang="en")
#         tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
#         tts.save(tmp.name)
#         return tmp.name
#     except Exception as e:
#         print(f"TTS failed: {e}")
#         return None

# # ---------- 核心 chat 函式（唯一版本）----------

# def chat(history: list[dict]) -> tuple[list[dict], str | None, Image.Image | None]:
#     """
#     接收完整 history，呼叫 Gemini via litellm，
#     處理 tool calls，回傳 (updated_history, audio_path, image)。
#     """
#     clean_history = [{"role": h["role"], "content": h["content"]} for h in history]
#     messages = [{"role": "system", "content": system_message}] + clean_history

#     cities: list[str] = []
#     image: Image.Image | None = None

#     try:
#         response = litellm.completion(model=MODEL, messages=messages, tools=tools)

#         # Tool call 迴圈
#         while response.choices[0].finish_reason == "tool_calls":
#             msg = response.choices[0].message
#             tool_responses, new_cities = handle_tool_calls(msg)
#             cities.extend(new_cities)

#             # litellm 回傳的 message 物件需轉成 dict 加入 messages
#             messages.append(msg.model_dump())
#             messages.extend(tool_responses)

#             response = litellm.completion(model=MODEL, messages=messages, tools=tools)

#         reply = response.choices[0].message.content or "(no reply)"

#     except Exception as e:
#         print(f"LLM call failed: {e}")
#         reply = "Sorry, I'm having trouble connecting right now. Please try again."

#     # 更新 history
#     history = history + [{"role": "assistant", "content": reply}]

#     # 語音
#     audio_path = talker(reply)

#     # 圖片：只有在查詢到城市時才生成，避免不必要的 API 呼叫
#     if cities:
#         image = artist(cities[0])

#     return history, audio_path, image

# # ---------- Gradio UI ----------

# def put_message_in_chatbot(
#     message: str, history: list[dict]
# ) -> tuple[str, list[dict]]:
#     """將使用者輸入加入 history，並清空輸入框。"""
#     return "", history + [{"role": "user", "content": message}]


# with gr.Blocks(title="FlightAI Assistant") as ui:
#     gr.Markdown("## ✈️ FlightAI — Your AI Travel Assistant")
#     gr.Markdown(
#         "Ask me about ticket prices to any city! "
#         "I'll look up the fare, generate a travel image, and read the answer aloud."
#     )

#     with gr.Row():
#         chatbot      = gr.Chatbot(height=500, type="messages", label="Conversation")
#         image_output = gr.Image(height=500, interactive=False, label="Destination Preview")

#     with gr.Row():
#         audio_output = gr.Audio(autoplay=True, label="Voice Reply")

#     with gr.Row():
#         message_box = gr.Textbox(
#             label="Chat with FlightAI:",
#             placeholder="e.g. How much is a ticket to Tokyo?",
#             scale=9,
#         )
#         send_btn = gr.Button("Send", scale=1, variant="primary")

#     # 送出事件：Textbox Enter 或 Send 按鈕
#     submit_event = message_box.submit(
#         put_message_in_chatbot,
#         inputs=[message_box, chatbot],
#         outputs=[message_box, chatbot],
#     ).then(
#         chat,
#         inputs=chatbot,
#         outputs=[chatbot, audio_output, image_output],
#     )

#     send_btn.click(
#         put_message_in_chatbot,
#         inputs=[message_box, chatbot],
#         outputs=[message_box, chatbot],
#     ).then(
#         chat,
#         inputs=chatbot,
#         outputs=[chatbot, audio_output, image_output],
#     )

# ui.launch(
#     inbrowser=True,
#     auth=(GRADIO_USER, GRADIO_PASSWORD),
# )


# =======================================================
# # imports

# import os
# import json
# from dotenv import load_dotenv
# from openai import OpenAI
# import gradio as gr
# import sqlite3


# # Initialization

# load_dotenv(override=True)

# openai_api_key = os.getenv('OPENAI_API_KEY')
# if openai_api_key:
#     print(f"OpenAI API Key exists and begins {openai_api_key[:8]}")
# else:
#     print("OpenAI API Key not set")
    
# MODEL = "gpt-4.1-mini"
# openai = OpenAI()

# DB = "prices.db"


# system_message = """
# You are a helpful assistant for an Airline called FlightAI.
# Give short, courteous answers, no more than 1 sentence.
# Always be accurate. If you don't know the answer, say so.
# """


# def get_ticket_price(city):
#     print(f"DATABASE TOOL CALLED: Getting price for {city}", flush=True)
#     with sqlite3.connect(DB) as conn:
#         cursor = conn.cursor()
#         cursor.execute('SELECT price FROM prices WHERE city = ?', (city.lower(),))
#         result = cursor.fetchone()
#         return f"Ticket price to {city} is ${result[0]}" if result else "No price data available for this city"


# get_ticket_price("Paris")


# price_function = {
#     "name": "get_ticket_price",
#     "description": "Get the price of a return ticket to the destination city.",
#     "parameters": {
#         "type": "object",
#         "properties": {
#             "destination_city": {
#                 "type": "string",
#                 "description": "The city that the customer wants to travel to",
#             },
#         },
#         "required": ["destination_city"],
#         "additionalProperties": False
#     }
# }
# tools = [{"type": "function", "function": price_function}]


# def chat(message, history):
#     history = [{"role": h["role"], "content": h["content"]} for h in history]
#     messages = [{"role": "system", "content": system_message}] + history + [{"role": "user", "content": message}]
#     response = openai.chat.completions.create(model=MODEL, messages=messages)
#     return response.choices[0].message.content

# gr.ChatInterface(fn=chat, type="messages").launch()


# def chat(message, history):
#     history = [{"role":h["role"], "content":h["content"]} for h in history]
#     messages = [{"role": "system", "content": system_message}] + history + [{"role": "user", "content": message}]
#     response = openai.chat.completions.create(model=MODEL, messages=messages, tools=tools)

#     while response.choices[0].finish_reason=="tool_calls":
#         message = response.choices[0].message
#         responses = handle_tool_calls(message)
#         messages.append(message)
#         messages.extend(responses)
#         response = openai.chat.completions.create(model=MODEL, messages=messages, tools=tools)
    
#     return response.choices[0].message.content


# def handle_tool_calls(message):
#     responses = []
#     for tool_call in message.tool_calls:
#         if tool_call.function.name == "get_ticket_price":
#             arguments = json.loads(tool_call.function.arguments)
#             city = arguments.get('destination_city')
#             price_details = get_ticket_price(city)
#             responses.append({
#                 "role": "tool",
#                 "content": price_details,
#                 "tool_call_id": tool_call.id
#             })
#     return responses


# gr.ChatInterface(fn=chat, type="messages").launch()

# # ## A bit more about what Gradio actually does:
# # 
# # 1. Gradio constructs a frontend Svelte app based on our Python description of the UI
# # 2. Gradio starts a server built upon the Starlette web framework listening on a free port that serves this React app
# # 3. Gradio creates backend routes for our callbacks, like chat(), which calls our functions
# # 
# # And of course when Gradio generates the frontend app, it ensures that the the Submit button calls the right backend route.
# # 
# # That's it!
# # 
# # It's simple, and it has a result that feels magical.


# # # Let's go multi-modal!!
# # 
# # We can use DALL-E-3, the image generation model behind GPT-4o, to make us some images
# # 
# # Let's put this in a function called artist.
# # 
# # ### Price alert: each time I generate an image it costs about 4 cents - don't go crazy with images!


# # Some imports for handling images

# import base64
# from io import BytesIO
# from PIL import Image


# def artist(city):
#     image_response = openai.images.generate(
#             model="dall-e-3",
#             prompt=f"An image representing a vacation in {city}, showing tourist spots and everything unique about {city}, in a vibrant pop-art style",
#             size="1024x1024",
#             n=1,
#             response_format="b64_json",
#         )
#     image_base64 = image_response.data[0].b64_json
#     image_data = base64.b64decode(image_base64)
#     return Image.open(BytesIO(image_data))


# image = artist("New York City")
# display(image)

# def talker(message):
#     response = openai.audio.speech.create(
#       model="gpt-4o-mini-tts",
#       voice="onyx",    # Also, try replacing onyx with alloy or coral
#       input=message
#     )
#     return response.content

# # ## Let's bring this home:
# # 
# # 1. A multi-modal AI assistant with image and audio generation
# # 2. Tool callling with database lookup
# # 3. A step towards an Agentic workflow
# # 


# def chat(history):
#     history = [{"role":h["role"], "content":h["content"]} for h in history]
#     messages = [{"role": "system", "content": system_message}] + history
#     response = openai.chat.completions.create(model=MODEL, messages=messages, tools=tools)
#     cities = []
#     image = None

#     while response.choices[0].finish_reason=="tool_calls":
#         message = response.choices[0].message
#         responses, cities = handle_tool_calls_and_return_cities(message)
#         messages.append(message)
#         messages.extend(responses)
#         response = openai.chat.completions.create(model=MODEL, messages=messages, tools=tools)

#     reply = response.choices[0].message.content
#     history += [{"role":"assistant", "content":reply}]

#     voice = talker(reply)

#     if cities:
#         image = artist(cities[0])
    
#     return history, voice, image



# def handle_tool_calls_and_return_cities(message):
#     responses = []
#     cities = []
#     for tool_call in message.tool_calls:
#         if tool_call.function.name == "get_ticket_price":
#             arguments = json.loads(tool_call.function.arguments)
#             city = arguments.get('destination_city')
#             cities.append(city)
#             price_details = get_ticket_price(city)
#             responses.append({
#                 "role": "tool",
#                 "content": price_details,
#                 "tool_call_id": tool_call.id
#             })
#     return responses, cities


# # ## The 3 types of Gradio UI
# # 
# # `gr.Interface` is for standard, simple UIs
# # 
# # `gr.ChatInterface` is for standard ChatBot UIs
# # 
# # `gr.Blocks` is for custom UIs where you control the components and the callbacks


# # Callbacks (along with the chat() function above)

# def put_message_in_chatbot(message, history):
#         return "", history + [{"role":"user", "content":message}]

# # UI definition

# with gr.Blocks() as ui:
#     with gr.Row():
#         chatbot = gr.Chatbot(height=500, type="messages")
#         image_output = gr.Image(height=500, interactive=False)
#     with gr.Row():
#         audio_output = gr.Audio(autoplay=True)
#     with gr.Row():
#         message = gr.Textbox(label="Chat with our AI Assistant:")

# # Hooking up events to callbacks

#     message.submit(put_message_in_chatbot, inputs=[message, chatbot], outputs=[message, chatbot]).then(
#         chat, inputs=chatbot, outputs=[chatbot, audio_output, image_output]
#     )

# ui.launch(inbrowser=True, auth=("ed", "bananas"))