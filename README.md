**Privacy Focused Local LLM With Internet Access**

A **privacy focused** local LLM implementation, with **customizable models, vector embeddings,** and **API-free live web search.**

# Features

- **Multi Format Support:** Supported document types include DOCX, PDF, and PPTX
- **Fully Private:** Runs entirely locally, which means no cloud server or external API keys are required
- **Local LLM inference:** Uses **Ollama** with **Qwen 2.5 7B/3B**
- **Semantic Search:** Uses **ChromaDB** for vector embeddings. This helps in faster retrieval, and was used for RAG implementation and optimization.
- **Optional Web Search Functionality:**
  -An **MCP web-search server** is integrated via **Node/NPM** to catch **Live Web Snippets.** It uses DuckDuckGo search integration. No external API keys are needed.

- **Persistent memory**: Document state persists across sessions
- **Uploading a doc is optional**

# Use Cases


**Students**: Query lecture notes, textbooks, research papers at **no additional cost  
Researchers**: Ask questions about your own papers and datasets  
**Professionals**: Search internal documentation privately  
**Developers**: Q&A over codebases and technical docs

# Prerequisites

- Python 3.8 and later
- Ollama installed and running
- 4+ GB RAM (This was implemented on 8 GB RAM)
- GPU - optional, recommended for Qwen 2.5 7B.

# Installation

- **Clone and install dependencies**

git clone &lt;your_repo_URL&gt;

cd custom_llm

pip install -r requirements.txt

-**Pull the Ollama model**

  -ollama pull qwen2.5:7b

  -if using 3b; ollama pull qwen2.5:3b

- **Run Ollama in the background**

  -ollama serve

- **Start the app**

  -streamlit run main1.py

- Open your browser to <http://localhost:8501>

# How to Use

- **Upload a document**
  - Click the file uploader and select a PDF, DOCX, or PPTX
  - The app extracts text and stores chunks in ChromaDB as vector embeddings
  - Status: " Processed \[filename\] into ChromaDB"
- **Ask a question**
  - Type your query in the text box
  - Optionally enable "Enable live web context (DuckDuckGo)?" for real-time info
  - Hit Enter or click the search button
- **Get context + answer**
  - App retrieves the 5 most relevant document chunks using semantic search
  - (Optional) Fetches live web results
  - Local LLM synthesizes a response using both contexts
  - Results appear with expandable context sections

# Tech Stack Used

| **Component**                         | **Purpose**                    |
| ------------------------------------- | ------------------------------ |
| **Streamlit**                         | Web UI framework               |
| **Ollama**                            | Local LLM inference engine     |
| **Qwen 2.5**                          | LLM model (7B or 3B)           |
| **ChromaDB**                          | Vector database for embeddings |
| **PyPDF / python-docx / python-pptx** | Document parsing               |
| **httpx + BeautifulSoup4**            | DuckDuckGo web scraping        |
| **Streamlit cache**                   | Session state management       |

# Project Structure

local-rag-assistant/

├── app.py # Main Streamlit app

├── requirements.txt # Python dependencies

├── README.md # This file

└── .gitignore # Git ignore rules

# System Prompts

AI hallucinations and LLM confusion are common issues. Instead of handling them at the output level, I focused on addressing their root causes.

To do this, I optimized the RAG pipeline and introduced a system prompt to guide how the model reasons and responds in plain language. This system prompt works like ChatGPT custom instructions and can be fully customized. A default version is included for the LLM to follow as a reference.

More info regarding system prompts can be found [here](https://medium.com/@adityaa9971/system-prompts-explained-what-they-are-how-they-work-and-how-to-write-them-properly-d91e3f611046)

# Model Selection

Edit app.py, line 252:

model="qwen2.5:7b", # Change to any local LLM model you want.

# Web Search Timeout

It adds a **fixed timer** for web searches.

If DuckDuckGo takes too long to respond (due to a slow internet connection, poor signal, or temporary server lag), your Streamlit app will sit there spinning infinitely.

By setting timeout = 10, you are telling the code: _"Try to scrape the web, but if it takes longer than 10 seconds, drop the request completely, throw a clean error message, and don't freeze my UI."_

Edit the call_web_search() function, line 20:

timeout=10, # Increase if DuckDuckGo searches time out

# Troubleshooting

**"Ollama error: connection refused"**

- **Problem**: Ollama not running
- **Fix**: Open a terminal and run ollama serve, keep it open

**"Model not found: qwen2.5:7b"**

- **Problem**: Model not pulled
- **Fix**: Run ollama pull qwen2.5:7b in terminal

**"Web search timed out"**

- **Problem**: DuckDuckGo request took too long
- **Fix**: Increase timeout in call_web_search() or disable web search

**"ChromaDB empty / No results retrieved"**

- **Problem**: Document didn't process correctly
- **Fix**: Check file format; try re-uploading; clear browser cache via Ctrl+Shift+Delete

**Streamlit app runs slowly**

- **Problem**: Running 7B model on CPU
- **Fix**: Switch to qwen2.5:3b or enable GPU acceleration

# How it's Private

- **No cloud uploads**: All inference happens locally on your machine
- **No API keys required** (except optional web search via DuckDuckGo)
- **No user tracking**: This app collects zero analytics
- **Secure document storage**: Embeddings stay in local ChromaDB only

# FAQ

**Q: Can I use this without Ollama?**  
A: No, you need Ollama for local inference. Alternatively, you could modify the code to use OpenAI API (costs money).

**Q: What documents does it support?**  
A: PDF, DOCX (Word), PPTX (PowerPoint). TXT and Markdown coming soon.

**Q: Is it accurate?**  
A: Accuracy depends on your document quality and model size. Qwen 2.5 7B is quite good; smaller models trade accuracy for speed.

**Q: Can I use a different LLM?**  
A: Yes! Any model in Ollama works. Change the model name in app.py and pull it first (ollama pull model_name).

**Q: Will this work on Windows/Mac/Linux?**  
A: Yes, if you have Python 3.8+, Ollama, and ~2GB free disk space.
