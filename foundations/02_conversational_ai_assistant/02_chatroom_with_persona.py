from litellm import completion
import gradio as gr

# ── Personality Templates ────────────────────────────────────────────────────

PERSONALITY_TEMPLATES = {
    "🤝 專業助理": "你是一位專業、嚴謹的助理。回應時請保持正式語氣，提供準確且有條理的資訊，避免不必要的閒聊。",
    "😊 輕鬆閒聊夥伴": "你是一個輕鬆、親切的聊天夥伴。用口語化、隨意的語氣回應，可以使用表情符號，讓對話感覺自然有趣。",
    "🎓 學術顧問": "你是一位嚴謹的學術顧問。回應時請引用邏輯與證據，使用精確的術語，並鼓勵深入思考與批判性分析。",
    "✍️ 創意寫作夥伴": "你是一位充滿創意的寫作夥伴。用豐富的想像力和生動的語言回應，鼓勵天馬行空的點子，幫助使用者探索故事與創作。",
    "🛠️ 技術工程師": "你是一位經驗豐富的軟體工程師。回應時請直接切入技術核心，提供具體的程式碼範例與解決方案，避免冗長的前言。",
    "🧘 心靈陪伴者": "你是一位溫柔、有耐心的傾聽者。回應時請展現同理心，先理解使用者的感受，再溫和地提供建議或支持。",
}

# ── Slider → Prompt Fragment Helpers ────────────────────────────────────────

def _formality(v):
    if v < 25:   return "請用非常輕鬆、口語化的方式回應，像朋友聊天一樣。"
    if v < 50:   return "請用自然、日常的語氣回應。"
    if v < 75:   return "請保持適度正式的語氣回應。"
    return "請保持嚴謹、正式的專業語氣回應。"

def _length(v):
    if v < 25:   return "回應請盡量簡短，只說重點。"
    if v < 50:   return "回應長度適中即可。"
    if v < 75:   return "回應請提供充足的說明與細節。"
    return "回應請盡量詳盡豐富，涵蓋各個面向。"

def _creativity(v):
    if v < 25:   return "回應請保守務實，以事實和邏輯為主。"
    if v < 50:   return "回應以實用為主，偶爾可加入有趣的類比。"
    if v < 75:   return "回應可以加入創意的比喻和有趣的角度。"
    return "回應請天馬行空、富有創意，鼓勵非傳統的思維。"

def _expertise(v):
    if v < 25:   return "請用淺顯易懂的語言回應，避免專業術語，適合初學者理解。"
    if v < 50:   return "請用一般大眾能理解的語言回應。"
    if v < 75:   return "可以使用適量的專業術語，假設使用者有一定背景知識。"
    return "請用專家對專家的方式回應，使用完整的專業術語與深度分析。"

def _proactivity(v):
    if v < 25:   return "請只回答使用者明確問到的問題，不要主動延伸。"
    if v < 50:   return "回答問題後，可以簡單補充相關資訊。"
    if v < 75:   return "回答後請主動提出相關的延伸建議或問題。"
    return "請積極主動地引導對話，提供延伸建議、追問細節，並主動推薦相關資源。"

def build_slider_prompt(formality, length, creativity, expertise, proactivity):
    parts = [
        "你是一個 AI 助理，請根據以下人格設定回應：",
        _formality(formality),
        _length(length),
        _creativity(creativity),
        _expertise(expertise),
        _proactivity(proactivity),
    ]
    return " ".join(parts)

# ── LLM Call ────────────────────────────────────────────────────────────────

def chat(message, history, system_prompt):
    messages = [{"role": "system", "content": system_prompt or "你是一個有幫助的助理。"}]
    for user_msg, assistant_msg in history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})
    messages.append({"role": "user", "content": message})

    try:
        response = completion(
            model="ollama/llama3.1:8b",
            messages=messages,
            base_url="http://localhost:11434"
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ 發生錯誤：{e}"

# ── Gradio UI ────────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg:        #0e0f11;
    --surface:   #16181c;
    --border:    #2a2d35;
    --accent:    #c8a96e;
    --accent2:   #7eb8c9;
    --text:      #e8e4dc;
    --muted:     #6b6f7a;
    --danger:    #c96e6e;
    --radius:    10px;
}

body, .gradio-container {
    background: var(--bg) !important;
    font-family: 'Noto Serif TC', serif !important;
    color: var(--text) !important;
}

/* Header */
.app-header {
    text-align: center;
    padding: 2rem 1rem 1rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.5rem;
}
.app-header h1 {
    font-size: 2rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    color: var(--accent);
    margin: 0;
}
.app-header p {
    color: var(--muted);
    font-size: 0.85rem;
    margin-top: 0.4rem;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.05em;
}

/* Panels */
.panel-label {
    font-size: 0.7rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
}

/* Tabs */
.tab-nav button {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.08em !important;
    color: var(--muted) !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    padding: 0.6rem 1rem !important;
    transition: all 0.2s !important;
}
.tab-nav button.selected {
    color: var(--accent) !important;
    border-bottom-color: var(--accent) !important;
}

/* Inputs */
textarea, input[type="text"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    font-family: 'Noto Serif TC', serif !important;
}
textarea:focus, input[type="text"]:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(200, 169, 110, 0.15) !important;
}

/* Chatbot */
.chatbot {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
}
.chatbot .message.user {
    background: rgba(200, 169, 110, 0.12) !important;
    border: 1px solid rgba(200, 169, 110, 0.2) !important;
    color: var(--text) !important;
}
.chatbot .message.bot {
    background: rgba(126, 184, 201, 0.08) !important;
    border: 1px solid rgba(126, 184, 201, 0.15) !important;
    color: var(--text) !important;
}

/* Buttons */
button.primary {
    background: var(--accent) !important;
    color: #0e0f11 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.1em !important;
    border: none !important;
    border-radius: var(--radius) !important;
    font-weight: 500 !important;
    transition: opacity 0.2s !important;
}
button.primary:hover { opacity: 0.85 !important; }

button.secondary {
    background: transparent !important;
    color: var(--muted) !important;
    border: 1px solid var(--border) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.78rem !important;
    border-radius: var(--radius) !important;
}
button.secondary:hover {
    border-color: var(--accent2) !important;
    color: var(--accent2) !important;
}

/* Slider */
input[type="range"] { accent-color: var(--accent) !important; }

/* Dropdown */
.dropdown {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
}

/* Active prompt preview */
.active-prompt {
    background: rgba(126, 184, 201, 0.06) !important;
    border: 1px solid rgba(126, 184, 201, 0.2) !important;
    border-left: 3px solid var(--accent2) !important;
    border-radius: var(--radius) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.78rem !important;
    color: var(--muted) !important;
}
"""

DEFAULT_SYSTEM = "你是一個有幫助的助理。"

with gr.Blocks(css=CSS, title="AI 聊天室") as demo:

    # ── State ──
    active_system = gr.State(DEFAULT_SYSTEM)

    # ── Header ──
    gr.HTML("""
    <div class="app-header">
        <h1>✦ AI 聊天室</h1>
        <p>local · llama3.1:8b · ollama</p>
    </div>
    """)

    with gr.Row():
        # ── Left: Personality Settings ──────────────────────────────────────
        with gr.Column(scale=2):
            gr.HTML('<div class="panel-label">人格設定</div>')

            with gr.Tabs():
                # Tab 1: Free text
                with gr.TabItem("✏️ 自由輸入"):
                    free_text = gr.Textbox(
                        label="System Prompt",
                        placeholder="直接描述 AI 的人格與行為，例如：你是一個說話簡潔的助理，專長是資料分析…",
                        lines=6,
                        value=DEFAULT_SYSTEM
                    )
                    apply_free = gr.Button("套用此設定", variant="primary")

                # Tab 2: Templates
                with gr.TabItem("📋 人格範本"):
                    template_dd = gr.Dropdown(
                        label="選擇範本",
                        choices=list(PERSONALITY_TEMPLATES.keys()),
                        value=None,
                        interactive=True
                    )
                    template_preview = gr.Textbox(
                        label="範本內容預覽",
                        lines=4,
                        interactive=False
                    )
                    apply_template = gr.Button("套用此設定", variant="primary")

                # Tab 3: Sliders
                with gr.TabItem("🎛️ 維度調整"):
                    s_formality   = gr.Slider(0, 100, value=50, label="語氣正式程度　口語 ↔ 正式")
                    s_length      = gr.Slider(0, 100, value=50, label="回應長度　　　精簡 ↔ 詳盡")
                    s_creativity  = gr.Slider(0, 100, value=50, label="創意程度　　　務實 ↔ 天馬行空")
                    s_expertise   = gr.Slider(0, 100, value=50, label="專業深度　　　入門 ↔ 專家")
                    s_proactivity = gr.Slider(0, 100, value=50, label="主動性　　　　被動 ↔ 積極引導")
                    apply_sliders = gr.Button("套用此設定", variant="primary")

            # Active prompt preview
            gr.HTML('<div class="panel-label" style="margin-top:1.25rem;">目前生效的 System Prompt</div>')
            active_preview = gr.Textbox(
                value=DEFAULT_SYSTEM,
                lines=3,
                interactive=False,
                elem_classes=["active-prompt"],
                show_label=False
            )

        # ── Right: Chat ──────────────────────────────────────────────────────
        with gr.Column(scale=3):
            gr.HTML('<div class="panel-label">對話</div>')
            chatbot = gr.Chatbot(height=480, show_label=False)
            with gr.Row():
                msg_input = gr.Textbox(
                    placeholder="輸入訊息，按 Enter 傳送…",
                    show_label=False,
                    scale=5,
                    lines=1
                )
                send_btn  = gr.Button("傳送", variant="primary", scale=1)
            clear_btn = gr.Button("清除對話紀錄", variant="secondary")

    # ── Event: Template preview ──────────────────────────────────────────────
    def on_template_select(choice):
        return PERSONALITY_TEMPLATES.get(choice, "")

    template_dd.change(on_template_select, inputs=template_dd, outputs=template_preview)

    # ── Event: Apply buttons ─────────────────────────────────────────────────
    def apply_free_fn(text):
        p = text.strip() or DEFAULT_SYSTEM
        return p, p

    def apply_template_fn(choice):
        p = PERSONALITY_TEMPLATES.get(choice, DEFAULT_SYSTEM)
        return p, p

    def apply_sliders_fn(f, l, c, e, p):
        prompt = build_slider_prompt(f, l, c, e, p)
        return prompt, prompt

    apply_free.click(apply_free_fn,
        inputs=[free_text],
        outputs=[active_system, active_preview])

    apply_template.click(apply_template_fn,
        inputs=[template_dd],
        outputs=[active_system, active_preview])

    apply_sliders.click(apply_sliders_fn,
        inputs=[s_formality, s_length, s_creativity, s_expertise, s_proactivity],
        outputs=[active_system, active_preview])

    # ── Event: Chat ──────────────────────────────────────────────────────────
    def respond(message, history, system_prompt):
        if not message.strip():
            return history, ""
        reply = chat(message, history, system_prompt)
        history = history + [(message, reply)]
        return history, ""

    send_btn.click(respond,
        inputs=[msg_input, chatbot, active_system],
        outputs=[chatbot, msg_input])

    msg_input.submit(respond,
        inputs=[msg_input, chatbot, active_system],
        outputs=[chatbot, msg_input])

    clear_btn.click(lambda: [], outputs=[chatbot])

demo.launch()