from pathlib import Path
import logging
from typing import Optional, List, Tuple
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

try:
    import ollama
except ImportError:
    ollama = None

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".css",
    ".js", ".ts", ".py", ".sql", ".log", ".rtf"
}
UNSUPPORTED_CONTAINER_EXTENSIONS = {".xlsx", ".xls", ".pptx", ".ppt", ".odt"}
ARTIFACT_MARKERS = {
    "pk", "[content_types].xml", "content_types", "_rels", "document.xml",
    "word/", "xl/", "ppt/", "rels", "docprops", "application/vnd.openxmlformats"
}
STOPWORDS = {
    "about", "after", "again", "against", "also", "and", "because", "before", "being",
    "between", "could", "does", "during", "for", "from", "have", "into", "more",
    "other", "over", "same", "some", "than", "that", "their", "there", "these",
    "this", "through", "under", "using", "were", "with", "would", "your"
}

def sanitize_filename(name: str, suffix: str) -> str:
    # Enforces a strict safe-naming convention to prevent filesystem errors
    # across different OSs (Windows/Mac/Linux) and avoid accidental path injection.
    if not name:
        return ""
    if name.lower().endswith(suffix.lower()):
        name = name[:-len(suffix)]
        
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    clean_name = re.sub(r'_+', '_', clean_name).strip('_')
    
    if not clean_name:
        clean_name = "ai_renamed_file"
        
    return f"{clean_name}{suffix}"

def _clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def _looks_like_package_artifacts(text: str) -> bool:
    lowered = text.lower()
    marker_hits = sum(1 for marker in ARTIFACT_MARKERS if marker in lowered)
    if marker_hits >= 2:
        return True

    tokens = re.findall(r"[A-Za-z0-9_\-/.\[\]]+", text)
    if not tokens:
        return True
    artifact_tokens = [
        token for token in tokens
        if "/" in token or "\\" in token or token.endswith(".xml") or token.lower() == "pk"
    ]
    return len(artifact_tokens) / len(tokens) > 0.25

def _word_is_readable(word: str) -> bool:
    if len(word) < 3:
        return False
    if len(word) > 18:
        return False
    vowels = sum(1 for char in word.lower() if char in "aeiou")
    return vowels > 0 and vowels / len(word) >= 0.2

def is_usable_text(text: str) -> bool:
    if not text:
        return False
    if _looks_like_package_artifacts(text):
        return False
    alpha_chars = re.findall(r"[A-Za-z]", text)
    if len(alpha_chars) < 20:
        return False
    readable_words = [w for w in re.findall(r"[A-Za-z]{3,}", text) if _word_is_readable(w)]
    if len(readable_words) < 4:
        return False
    return len(readable_words) / max(1, len(re.findall(r"[A-Za-z]{3,}", text))) >= 0.55

def _extract_docx_text(file_path: Path, max_chars: int) -> str:
    try:
        with zipfile.ZipFile(file_path) as archive:
            with archive.open("word/document.xml") as document:
                root = ET.fromstring(document.read())
    except Exception as e:
        logging.error(f"Error extracting DOCX text from {file_path}: {e}")
        return ""

    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    chunks = []
    for node in root.iter(f"{namespace}t"):
        if node.text:
            chunks.append(node.text)
            if sum(len(chunk) for chunk in chunks) >= max_chars:
                break
    return _clean_text(" ".join(chunks))[:max_chars]

def extract_text_from_image(file_path: Path) -> str:
    # Uses OCR to 'see' inside images, allowing us to categorize screenshots
    # or photos based on their textual content rather than just visual pixels.
    try:
        import pytesseract
        from PIL import Image
        
        logging.info(f"Running Tesseract OCR on image: {file_path.name}")
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        
        if not text.strip():
            return ""
            
        return f"Extracted OCR Text from Image: {text.strip()}"
    except ImportError:
        logging.error("pytesseract or Pillow not installed. Cannot run OCR.")
        return ""
    except Exception as e:
        logging.error(f"Tesseract OCR failed for {file_path.name}. Is tesseract installed on your system? Error: {e}")
        return ""

def extract_text(file_path: Path, max_chars: int = 2000) -> str:
    # Unified text extraction gateway. We limit characters (2000) to prevent 
    # overloading the LLM context window while still capturing the core intent.
    text = ""
    try:
        suffix = file_path.suffix.lower()
        if suffix in ['.jpg', '.jpeg', '.png', '.webp', '.heic']:
            text = extract_text_from_image(file_path)
        elif suffix == '.pdf':
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text += (page.extract_text() or "") + " "
                    if len(text) > max_chars:
                        break
            except ImportError:
                logging.warning("PyPDF2 not installed. Cannot read PDF.")
        elif suffix == ".docx":
            text = _extract_docx_text(file_path, max_chars)
        elif suffix in UNSUPPORTED_CONTAINER_EXTENSIONS:
            return ""
        elif suffix in TEXT_EXTENSIONS:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read(max_chars)
        else:
            return ""
    except Exception as e:
        logging.error(f"Error extracting text from {file_path}: {e}")
    
    text = _clean_text(text[:max_chars])
    return text if is_usable_text(text) else ""

class LocalLLM:
    # Gateway for local intelligence. We prefer local-first (Ollama/TF-IDF)
    # to maintain user privacy and avoid API costs/latency.
    def __init__(self, model: str = "llama3.2", use_ollama: bool = False):
        self.model = model
        self.use_ollama = use_ollama

    def extract_keywords(self, text: str) -> str:
        # Fallback mechanism when Ollama is unavailable.
        # It intentionally prefers no rename over a noisy or artifact-based name.
        try:
            if not is_usable_text(text):
                return ""

            words = [
                word.lower()
                for word in re.findall(r"[A-Za-z]{3,}", text)
                if word.lower() not in STOPWORDS and _word_is_readable(word)
            ]
            if len(words) < 4:
                return ""

            top_words = []
            for word, _count in Counter(words).most_common(8):
                if word not in top_words:
                    top_words.append(word)
                if len(top_words) == 4:
                    break

            if len(top_words) < 2:
                return ""

            top_words = [w.capitalize() for w in top_words[:4]]
            return "_".join(top_words)
        except Exception as e:
            logging.error(f"Keyword extraction failed: {e}")
            return ""

    def hyde_query(self, raw_query: str) -> str:
        """Generate a local hypothetical answer document for retrieval."""
        if not self.use_ollama:
            return raw_query
        if ollama is None:
            logging.error("Ollama package is not installed. Cannot run HyDE query rewrite.")
            return raw_query

        prompt = f"""
        Write a short, factual document that would answer this search query.
        Use concrete terms likely to appear in relevant local files.
        Do not add commentary.

        Query:
        {raw_query}
        """
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
            )
            content = response.get('message', {}).get('content', '').strip()
            return content or raw_query
        except Exception as e:
            logging.error(f"HyDE query rewrite failed: {e}")
            return raw_query

    def analyze_and_rename(self, file_path: Path, categories: List[str]) -> Tuple[Optional[str], Optional[str]]:
        # High-level logic that decides whether to use deep LLM analysis 
        # or fast mathematical keyword extraction.
        text = extract_text(file_path)
        if not text:
            return None, None
            
        if not self.use_ollama:
            # Fast, shippable keyword extraction (no GPU required).
            keywords = self.extract_keywords(text)
            new_name = None
            if keywords:
                new_name = sanitize_filename(f"{keywords}{file_path.suffix}", file_path.suffix)
            return None, new_name

        if ollama is None:
            logging.error("Ollama package is not installed. Cannot run local LLM rename.")
            return None, None

        # The prompt is engineered to force a structured JSON response, 
        # reducing the need for complex string parsing of AI output.
        prompt = f"""
        You are a file naming assistant. Your goal is to name files based ONLY on the text content provided below.
        
        Rules:
        - Analyze the text provided below.
        - Create a filename (WITHOUT extension) based ON THE TEXT provided. 
        - DO NOT add external information, interpret visual context beyond the text, or use general knowledge.
        - If the text is empty, contains mostly noise, or is unreadable, return 'Untitled_Document'.
        - Keep the name under 5 words, professional, and use underscores.
        - Category MUST be chosen from: {categories}.

        Text to analyze:
        {text}

        Respond ONLY with a valid JSON object in this exact format:
        {{"category": "CategoryName", "filename": "short_name"}}
        """
        
        try:
            response = ollama.chat(model=self.model, messages=[{'role': 'user', 'content': prompt}], format='json')
            content = response['message']['content']
            # Basic parsing: find the first { and last } to extract JSON if LLM adds chatter
            import json
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if not match:
                raise ValueError("No JSON found in response")
            data = json.loads(match.group(0))
            
            category = data.get("category")
            name_no_ext = data.get("filename")
            
            if name_no_ext:
                new_name = sanitize_filename(f"{name_no_ext}{file_path.suffix}", file_path.suffix)
            else:
                return None, None
            
            if category not in categories:
                category = None
            
            return category, new_name
            
        except Exception as e:
            logging.error(f"LLM processing failed for {file_path.name}: {e}")
            return None, None
