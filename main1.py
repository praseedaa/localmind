import streamlit as st
import chromadb
from pypdf import PdfReader
from docx import Document
from pptx import Presentation
import os
import ollama
import httpx
from bs4 import BeautifulSoup


def call_web_search(query: str, max_results: int = 5) -> str:
    """
    Scrapes DuckDuckGo HTML search results.
    Returns a plain-text summary of top snippets for use as RAG context.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=10,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.TimeoutException:
        return "Web search timed out. Try again."
    except httpx.HTTPStatusError as e:
        return f"Web search HTTP error: {e.response.status_code}"
    except Exception as e:
        return f"Web search error: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for result in soup.select(".result")[:max_results]:
        title_el = result.select_one(".result__title")
        snippet_el = result.select_one(".result__snippet")
        url_el = result.select_one(".result__url")

        title   = title_el.get_text(strip=True)   if title_el   else ""
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
        url     = url_el.get_text(strip=True)     if url_el     else ""

        if snippet:
            results.append(f"• {title}\n  {snippet}\n  ({url})")

    if not results:
        return "No web results found."

    return "\n\n".join(results)


def extract_keywords(text: str, num_keywords: int = 5) -> list:
    """
    Extract important keywords from text.
    Filters out common stop words and returns key terms.
    """
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "this", "that", "these", "those",
        "it", "its", "they", "them", "you", "your", "i", "me", "we", "us",
        "not", "no", "yes", "just", "also", "very", "so", "as", "more", "most"
    }
    
    # Extract words longer than 4 chars that aren't stop words
    words = [
        w.lower().strip('.,!?;:') 
        for w in text.split() 
        if len(w) > 4 and w.lower().strip('.,!?;:') not in stop_words
    ]
    
    # Return first N unique keywords
    seen = set()
    keywords = []
    for w in words:
        if w not in seen and w.isalpha():
            keywords.append(w)
            seen.add(w)
            if len(keywords) >= num_keywords:
                break
    
    return keywords


# Generic document-summary phrases that should always trigger enhancement
# even though they contain no document-specific keywords
GENERIC_DOC_PHRASES = [
    "what is this", "what's this", "what is the document", "what does this",
    "summarize", "summary", "tell me about", "explain this", "what about this",
    "what is it about", "give me an overview", "overview of", "about this doc",
    "what does it say", "what is this about", "describe this", "brief me",
]


def check_query_relevance(user_query: str, doc_keywords: list) -> bool:
    """
    Check if user's question is related to the document's topic.

    Returns True if:
    - The query is a generic document-summary phrase
      (e.g. "what is this doc about?" has no keywords but is clearly about the doc)
    - OR at least one document keyword appears in the query
    """
    query_lower = user_query.lower()

    # Check for generic document-summary intent first
    for phrase in GENERIC_DOC_PHRASES:
        if phrase in query_lower:
            return True

    # Check for keyword overlap
    for keyword in doc_keywords:
        if keyword.lower() in query_lower:
            return True

    return False


def build_smart_search_query(
    user_query: str,
    document_context: str = "",
    uploaded_this_session: bool = False,  # Bug 1 fix: session upload, not ChromaDB state
) -> tuple:
    """
    Build an intelligent web search query.

    Returns: (search_query, was_enhanced, explanation)

    Logic:
    - Only consider document context if user UPLOADED something this session.
      Prevents stale persistent ChromaDB data from silently affecting new sessions.
    - If uploaded this session: extract keywords, check relevance
        - Generic doc question OR keyword match → enhance search
        - Unrelated question → use query as-is
    - No upload this session → use query as-is
    """
    if uploaded_this_session and document_context.strip():
        doc_keywords = extract_keywords(document_context, num_keywords=3)

        if doc_keywords:
            is_relevant = check_query_relevance(user_query, doc_keywords)

            if is_relevant:
                smart_query = f"{' '.join(doc_keywords)} {user_query}"
                return smart_query.strip(), True, "Enhanced with document keywords"
            else:
                return user_query, False, "Query unrelated to document — searching as-is"

    return user_query, False, "No document uploaded this session — searching as-is"


# File parsers

def extract_pdf_text(file):
    try:
        reader = PdfReader(file)
        chunks = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                chunks.append({
                    "text": text.strip(),
                    "chunk_id": f"page_{i + 1}",
                    "metadata": {"page": i + 1},
                })
        return chunks
    except Exception as e:
        st.error(f"PDF read error: {e}")
        return []


def extract_docx_text(file):
    try:
        doc = Document(file)
        chunks = []
        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if text:
                chunks.append({
                    "text": text,
                    "chunk_id": f"paragraph_{i + 1}",
                    "metadata": {"page": i + 1},
                })
        return chunks
    except Exception as e:
        st.error(f"DOCX read error: {e}")
        return []


def extract_pptx_text(file):
    try:
        prs = Presentation(file)
        chunks = []
        for i, slide in enumerate(prs.slides):
            parts = [
                shape.text.strip()
                for shape in slide.shapes
                if hasattr(shape, "text") and shape.text.strip()
            ]
            if parts:
                chunks.append({
                    "text": "\n".join(parts),
                    "chunk_id": f"slide_{i + 1}",
                    "metadata": {"page": i + 1},
                })
        return chunks
    except Exception as e:
        st.error(f"PPTX read error: {e}")
        return []


# ChromaDB with PERSISTENT storage

@st.cache_resource
def get_collection():
    """
    Initialize ChromaDB with persistent storage.
    Documents will be saved to ./chroma_data/ folder.
    """
    client = chromadb.PersistentClient(path="./chroma_data")
    return client.get_or_create_collection(
        name="documents",
        metadata={"hnsw:space": "cosine"}
    )


def count_documents_in_collection(collection) -> int:
    """
    Returns the total number of document chunks stored in ChromaDB.
    """
    try:
        return collection.count()
    except Exception:
        return 0


st.title("LocalMind - Adaptive Local LLM Assistant")
st.write("Localmind is a local, privacy-first AI assistant. It runs entirely on your hardware. Query uploaded documents locally, tap into live web intelligence with API-free search, or use it as a completely secure, offline brainstorming partner—all powered by local LLMs.")
# Sidebar config
st.sidebar.title("Configuration")
default_system_prompt = (
    "You are a helpful assistant. Answer the user's question accurately using the provided "
    "local document context and any live web search insights. Synthesize clearly. "
    "If the answer cannot be found in either context, say so."
)
system_prompt = st.sidebar.text_area(
    "System Prompt",
    value=default_system_prompt,
    height=200,
)

# File upload
uploaded_file = st.file_uploader("Upload your file (optional)", type=["pdf", "docx", "pptx"])

collection = get_collection()

# Show how many documents are stored
doc_count = count_documents_in_collection(collection)
st.sidebar.info(f"Stored chunks: **{doc_count}**")

if uploaded_file is not None:
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    ext = os.path.splitext(uploaded_file.name)[1].lower()

    if "processed_files" not in st.session_state:
        st.session_state["processed_files"] = set()

    if file_key not in st.session_state["processed_files"]:
        parser_map = {
            ".pdf": extract_pdf_text,
            ".docx": extract_docx_text,
            ".pptx": extract_pptx_text,
        }
        chunks = parser_map.get(ext, lambda f: [])(uploaded_file)

        if chunks:
            st.write(f"Processing {len(chunks)} chunks from **{uploaded_file.name}**...")
            
            for item in chunks:
                item["metadata"]["source"] = uploaded_file.name
                try:
                    collection.add(
                        documents=[item["text"]],
                        metadatas=[item["metadata"]],
                        ids=[f"{uploaded_file.name}_{item['chunk_id']}"],
                    )
                except Exception as e:
                    pass  # Duplicate IDs are fine on rerun

            st.success(f" Stored **{len(chunks)}** chunks from **{uploaded_file.name}**.")
            st.session_state["processed_files"].add(file_key)
            
            # Refresh document count display
            doc_count = count_documents_in_collection(collection)
            st.sidebar.info(f"Stored chunks: **{doc_count}**")
        else:
            st.error("No text extracted — unsupported file or empty content.")

# Query
user_query = st.text_input("Ask something (with or without a document uploaded):")
enable_web = st.checkbox("Enable adaptive web search?")

if user_query:

    # 1. Retrieve local context from ChromaDB (if documents exist)
    local_context = ""
    retrieved_docs = []
    has_document_context = False
    
    try:
        results = collection.query(query_texts=[user_query], n_results=5)
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        
        if docs:
            has_document_context = True
            local_context = " ".join(docs)
            retrieved_docs = list(zip(docs, metadatas))
            
            with st.expander(f"Retrieved {len(docs)} document chunks"):
                for i, (doc, meta) in enumerate(retrieved_docs, 1):
                    st.write(f"**Chunk {i}** (from {meta.get('source', 'Unknown')} - Page {meta.get('page', '?')})")
                    st.write(doc[:300] + "..." if len(doc) > 300 else doc)
                    st.divider()
    except Exception as e:
        pass  # No documents in collection is fine


    # 2. Optional ADAPTIVE web search
    web_context = ""
    if enable_web:
        # Bug 1 fix: use session upload flag, not ChromaDB retrieval state
        uploaded_this_session = bool(st.session_state.get("processed_files"))

        search_query, was_enhanced, explanation = build_smart_search_query(
            user_query, local_context, uploaded_this_session
        )
        
        # Show what's happening
        st.info(f" {explanation}")
        if was_enhanced:
            with st.caption("Enhanced search query:"):
                st.code(search_query)
        
        with st.spinner("Searching the web..."):
            raw = call_web_search(search_query)
        
        if "error" in raw.lower() or "timed out" in raw.lower():
            st.error(raw)
        elif raw.strip() and raw != "No web results found.":
            web_context = raw
            with st.expander("Live web context"):
                st.write(web_context)
        else:
            st.warning("No web results returned.")

    # 3. Build final prompt
    has_context = bool(local_context.strip() or web_context.strip())

    if not has_context:
        st.warning("No context available. Using general knowledge only.")
        active_system = (
            "You are a helpful AI assistant. Answer using your general knowledge — "
            "no document or web context is available right now."
        )
        prompt = f"Question: {user_query}"
    else:
        active_system = system_prompt
        combined = (local_context + "\n\n" + web_context)[:4000]
        prompt = f"Context:\n{combined}\n\nQuestion: {user_query}"

    # 4. Call Ollama
    with st.spinner("Generating response..."):
        try:
            response = ollama.chat(
                model="qwen2.5:7b",
                messages=[
                    {"role": "system", "content": active_system},
                    {"role": "user", "content": prompt},
                ],
                options={
                    "num_predict": 400,
                    "temperature": 0.7,
                },
            )

            # Access Ollama response correctly
            content = (
                response.message.content
                if hasattr(response, "message")
                else response["message"]["content"]
            )

            st.subheader("Response")
            st.write(content)

        except Exception as e:
            st.error(f"Ollama error: {e}")
            st.info("Make sure Ollama is running: `ollama serve` and model is pulled: `ollama pull qwen2.5:7b`")
