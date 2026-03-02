# =============================================================================
# FlightAI Assistant V2
# Key optimizations based on the original :
#   1. Uses litellm for unified LLM calls, supporting quick switching between local and cloud models
#       - Local: ollama/ministral-3:8b, ollama/gemma3:4b, ollama/llama3.2:latest, etc.
#       - Cloud: gemini/gemini-2.5-flash
#   2. Tool calls now include an anti-infinite loop mechanism (MAX_TOOL_ROUNDS) and complete error handling.
#   3. Fix local model fail to recieve tool call reponse within the "messages"
#   4. Image generation now uses Cloudflare Workers AI (flux-1-schnell), which is free and offers better privacy.
#   5. Voice is now handled by gTTS (free), replacing OpenAI TTS.
#   6. Sensitive information (account password, API Key) is now read from environment variables.

# Environment variables (.env):
#   GOOGLE_API_KEY=...                # Google Gemini API Key
#   CLOUDFLARE_ACCOUNT_ID=...         # Cloudflare account ID
#   CLOUDFLARE_API_TOKEN=...          # Cloudflare API Token (Permission: Workers AI Read)
#   GRADIO_USER=...                   # Gradio login account
#   GRADIO_PASSWORD=...               # Gradio login password

# If using a local model, prerequisites:
#   ollama pull <model>               # e.g., ollama/ministral-3:8b, ollama/gemma3:4b, ollama/llama3.2:latest, etc.
#   ollama serve                      # Ensure the service is running at localhost:11434
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
from gtts import gTTS          
import litellm                 
import requests
import logging
               

# ---------- Initialization ----------
load_dotenv(override=True)

# Gradio login username and password are read from environment variables; 
# the default values ​​are only available for local development.
GRADIO_USER     = os.getenv("GRADIO_USER", "admin")
GRADIO_PASSWORD = os.getenv("GRADIO_PASSWORD", "changeme")

# logging setting
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# Option 1: Go with local model
#   litellm calls the local model through Ollama without any API key
#   Ensure the Ollama service is running: ollama serve

MODEL = "ollama/ministral-3:8b"
litellm.api_base = "http://localhost:11434"  # Ollama Default Port

# Option2: Go with cloud model
# MODEL = "gemini/gemini-2.5-flash"
# os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")
# litellm.api_key = os.getenv("GOOGLE_API_KEY")

# print(f"Using model: {MODEL} via Ollama")
logging.info(f"Using model: {MODEL} via Ollama")

system_message = """
You are a helpful assistant for an Airline called FlightAI.
Give short, courteous answers, no more than 1 sentence.
Always be accurate. If you don't know the answer, say so.

IMPORTANT - Tool usage rules:
1. When you need price information, call the get_ticket_price tool ONCE. If you don't need price information, response directly.
2. After receiving a tool result, you MUST use that result to answer the user.
3. NEVER call the same tool twice in a row.
4. When you see a message with role "tool", that is the answer from the tool - use it immediately to respond.
"""


# ---------- Database ----------

DB = "prices.db"

def init_db():
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS prices (city TEXT PRIMARY KEY, price REAL)')
        conn.commit()

init_db()

# Preset ticket price information
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

# print("Database initialization complete")
logging.info("Database initialization complete")


# ---------- Tool Definition ----------
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

# ---------- Tool Functions ----------

def get_ticket_price(city: str) -> str:
    """Query fares from SQLite, including full error handling."""
    if not city:
        return "City name is missing."
    # print(f"DATABASE TOOL CALLED: Getting price for {city}", flush=True)
    logging.info(f"Database tool called: Getting price for {city}")
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
        # print(f"DB error: {e}")
        logging.error(f"DB error: {e}")
        return "Sorry, the price database is currently unavailable."


def handle_tool_calls(message) -> tuple[list[dict], list[str]]:
    """
    Process all tool calls and return (tool_responses, cities).
    The cities are used for subsequent image generation.
    """
    responses: list[dict] = []
    cities:    list[str]  = []

    for tool_call in (message.tool_calls or []):
        if tool_call.function.name == "get_ticket_price":
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                # print(f"JSON parse error: {e}")
                logging.error(f"JSON parse error: {e}")
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

# ---------- Multimedia function ----------

CF_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN  = os.getenv("CLOUDFLARE_API_TOKEN")

import base64

def artist(city: str) -> Image.Image | None:
    try:
        url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{CF_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"
        )
        headers = {"Authorization": f"Bearer {CF_API_TOKEN}"}
        payload = {
            "prompt": (
                f"A vibrant pop-art style travel poster for {city}, "
                f"showcasing famous tourist spots and local culture of {city}."
            ),
            "num_steps": 4,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()

        image_base64 = resp.json()["result"]["image"]
        image_data = base64.b64decode(image_base64)
        return Image.open(BytesIO(image_data))
    except Exception as e:
        # print(f"Image generation failed: {e}")
        logging.error(f"Image generation failed: {e}")
        return None


def talker(text: str) -> str | None:
    """
    Use gTTS to convert text to speech and upload the temporary .mp3 file to the specified path.
    Return None on failure.
    """
    try:
        tts = gTTS(text=text, lang="en")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp.name)
        return tmp.name
    except Exception as e:
        # print(f"TTS failed: {e}")
        logging.error(f"TTS failed: {e}")
        return None

# ---------- Core chat function ----------

def chat(history: list[dict]) -> tuple[list[dict], str | None, Image.Image | None]:
    """
    Receive complete history, call Gemini via litellm.
    Process tool calls and return (updated_history, audio_path, image).
    """
    clean_history = [{"role": h["role"], "content": h["content"]} for h in history]
    messages = [{"role": "system", "content": system_message}] + clean_history

    cities: list[str] = []
    image: Image.Image | None = None

    try:
        response = litellm.completion(model=MODEL, messages=messages, tools=tools)

        # Tool call loop
        MAX_TOOL_ROUNDS = 5
        tool_rounds = 0

        while (
            response.choices[0].finish_reason == "tool_calls"
            or response.choices[0].message.tool_calls  # Some local models have inaccurate finish_reason.
        ) and tool_rounds < MAX_TOOL_ROUNDS:
            
            msg = response.choices[0].message
            if not msg.tool_calls:  # Force exit if there are no tool calls
                break
                
            tool_responses, new_cities = handle_tool_calls(msg)
            cities.extend(new_cities)
            
            # dump as a python dict
            messages.append(msg.model_dump())
            
            messages.extend(tool_responses)
            
            
            # calling the model with tools = tools again, for smaller model might struggle with fetching tool response in the "messages" and return None in content, thus set tools = None
            # Also, append a extra user message to force the model to check the tool response inside the "messages" might help too
            messages.append({
                "role": "user",
                "content": "Tool result received. Please answer now."
            })
                        
            # response = litellm.completion(model=MODEL, messages=messages, tools=tools)
            response = litellm.completion(model=MODEL, messages=messages, tools=None)
            
            tool_rounds += 1
            
            if response.choices[0].message.content:
                break

        reply = response.choices[0].message.content or "(no reply)"

    except Exception as e:
        # print(f"LLM call failed: {e}")
        logging.error(f"LLM call failed: {e}")
        reply = "Sorry, I'm having trouble connecting right now. Please try again."

    # update history
    history = history + [{"role": "assistant", "content": reply}]

    # voice
    audio_path = talker(reply)

    # Image: Only generated when a city is found, avoiding unnecessary API calls.
    
    if cities:
        image = artist(cities[0])

    return history, audio_path, image

# ---------- Gradio UI ----------

def put_message_in_chatbot(
    message: str, history: list[dict]
) -> tuple[str, list[dict]]:
    """Add user input to history and clear the input field."""
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

    # Send event: Textbox Enter or Send button
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
    
    # uncomment it when needed
    # auth=(GRADIO_USER, GRADIO_PASSWORD),
)