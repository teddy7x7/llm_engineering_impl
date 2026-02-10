# LLM Engineering — From Fundamentals to Production Patterns

This repository documents my hands-on exploration of **Large Language Model (LLM) engineering**, focusing on how to design, evaluate, and iterate on LLM-powered systems beyond simple prompt + API usage.

The work here is **inspired by** (but not copied from) the excellent
[ed-donner/llm_engineering](https://github.com/ed-donner/llm_engineering) curriculum.
All implementations are reworked, extended, or adapted with my own design decisions, tooling choices, and experiments.

---

## 🎯 Project Goals

This repo is built as a **learning + portfolio project**, with the following goals:

* Understand **core LLM system design patterns**, not just model APIs
* Gain hands-on experience with:

  * Prompt engineering
  * Retrieval-Augmented Generation (RAG)
  * Open / free model workflows
  * Agent-style reasoning and tool usage

* Practice **engineering trade-offs**: latency, cost, accuracy, maintainability
* Build a codebase that reflects **how I think as an engineer**

---

## 🚀 What This Repository Covers

This repository covers the full lifecycle of LLM-powered products — from model selection and prototyping to training, evaluation, and deployment.

### 1. Transformer & LLM Foundations
- Understanding transformer architecture and inference behavior
- Hands-on experiments with multiple frontier and open-source models
- Observing differences in latency, reasoning, and output quality

### 2. Prompt Engineering & Structured Outputs
- Prompt templating and reuse
- Few-shot vs zero-shot trade-offs
- Reliable output formatting for downstream systems

### 3. Multi-Modal LLM Applications
- Text, image, and audio-based inputs
- Building agents that reason across modalities
- Real-world use cases such as customer support and meeting summarization

### 4. Retrieval-Augmented Generation (RAG)
- Embedding generation and vector search
- Chunking strategy comparisons
- Retrieval quality evaluation and tuning
- End-to-end knowledge worker systems

### 5. Code Generation & Performance-Oriented LLM Use
- Using LLMs for code translation and optimization
- Python → C++ code generation
- Measuring and validating real performance gains

### 6. Training & Fine-Tuning
- Fine-tuning frontier models for domain-specific tasks
- Advanced techniques such as parameter-efficient fine-tuning (e.g. QLoRA)
- Comparing fine-tuned open-source models against frontier baselines

### 7. Agents, Automation & Deployment
- Tool-using and multi-agent systems
- Decision-making loops and orchestration
- Deploying production-ready LLM applications with UI

---

## 🧠 Key Engineering Takeaways

What I deliberately focused on while building this repo:

* **Design intent > raw results**
  Each module documents *why* a pattern is used, not just *how*.

* **Evaluation matters**
  I experimented with simple evaluation heuristics (retrieval accuracy, answer relevance) instead of relying on subjective judgment.

* **Cost & constraints are real**
  Many examples are built with free-tier or open models to simulate real-world limitations.

---

## 🧩 Representative Projects

Some of the concrete systems built in this repository include:

- **AI-Powered Brochure Generator**  
  An agent that intelligently scrapes company websites, reasons over content, and generates structured sales brochures.

- **Multi-Modal Customer Support Agent**  
  A customer service assistant capable of handling text, images, and audio, with tool-calling and UI integration.

- **Meeting Minutes & Action Item Generator**  
  A system that processes audio recordings and produces structured summaries using both open-source and hosted models.

- **LLM-Based Code Translator (Python → C++)**  
  An automated pipeline that translates Python code into optimized C++, achieving orders-of-magnitude performance improvements.

- **RAG-Based Knowledge Worker**  
  A domain expert assistant that retrieves and reasons over internal documents using vector databases.

- **Autonomous Multi-Agent Deal Finder (Capstone)**  
  A collaborative agent system that monitors opportunities, evaluates deals, and sends notifications.

---

## 🛠️ Tech Stack

### Core Tooling

| Category            | Tools                                                  |
| ------------------- | ------------------------------------------------------ |
| **Language**        | Python 3.10+                                           |
| **Environment**     | **uv** (fast, modern Python dependency & venv manager) |
| **LLM Frameworks**  | LangChain / LlamaIndex                                 |
| **Vector Stores**   | ChromaDB                                               |
| **Data Processing** | Pandas, JSON, PDF loaders                              |
| **UI / Demos**      | Streamlit (where applicable)                           |

### Models

* Primarily **free or open-source models**
* Some optional experiments reference hosted APIs for comparison
* Model selection is treated as an engineering decision rather than a fixed dependency.
Both frontier and open-source models are evaluated based on task requirements,
cost, latency, and controllability.

---

<!-- ## 📂 Repository Structure

```
.
├── 01_prompt_engineering/
│   ├── prompt_patterns.py
│   └── experiments.md
│
├── 02_rag/
│   ├── loaders/
│   ├── chunking_strategies/
│   └── retrieval_tests/
│
├── 03_agents/
│   ├── tool_use/
│   └── control_flow/
│
├── projects/
│   └── end_to_end_apps/
│
└── notes/
    └── design_decisions.md
```

Each directory contains:

* runnable code
* short explanations
* notes on what worked / what didn’t

--- -->

## ⚙️ Getting Started

### Prerequisites

* Python 3.10+
* `uv` installed
  👉 [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)

---

### Setup

1. **Clone the repository**

```bash
git clone https://github.com/teddy7x7/llm_engineering_impl.git
cd llm_engineering
```

2. **Create and sync environment with uv**

```bash
uv venv
uv sync
```

3. **Activate the environment**

```bash
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate
```

4. **(Optional) Environment variables**
   If using any hosted APIs, create a `.env` file:

```env
OPENAI_API_KEY=your_key_here
```

Most examples are designed to work **without paid APIs**.

<!-- ---

## 📌 How to Read This Repo (for Reviewers)

If you're reviewing this as a portfolio project:

1. Start with `notes/design_decisions.md`
2. Look at `02_rag/` for system-level thinking
3. Check `projects/` for end-to-end integration
4. Skim commit history to see iteration patterns -->

---

## 🙏 Acknowledgments

* **Ed Donner** — for the original LLM Engineering curriculum and inspiration
  [https://github.com/ed-donner/llm_engineering](https://github.com/ed-donner/llm_engineering)

This repository is **not a fork**, but an independent implementation created as part of my learning and professional development.