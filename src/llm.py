import ollama
from pathlib import Path
import logging
from typing import Optional, List, Tuple
import json
import re

def sanitize_filename(name: str, suffix: str) -> str:
    """Sanitizes an AI-generated filename to prevent OS errors and enforce safe formatting."""
    if not name:
        return ""
    # Strip existing extension if AI included it
    if name.lower().endswith(suffix.lower()):
        name = name[:-len(suffix)]
        
    # Replace dangerous characters (like / \ : * ? " < > |) with underscores
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    clean_name = re.sub(r'_+', '_', clean_name).strip('_')
    
    if not clean_name:
        clean_name = "ai_renamed_file"
        
    return f"{clean_name}{suffix}"

def extract_text_from_image(file_path: Path) -> str:
    """Uses Tesseract OCR to perform text extraction on images."""
    try:
        import pytesseract
        from PIL import Image
        
        logging.info(f"Running Tesseract OCR on image: {file_path.name}")
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        
        if not text.strip():
            return "This is a photo or image with no readable text."
            
        return f"Extracted OCR Text from Image: {text.strip()}"
    except ImportError:
        logging.error("pytesseract or Pillow not installed. Cannot run OCR.")
        return "Image with no readable text."
    except Exception as e:
        logging.error(f"Tesseract OCR failed for {file_path.name}. Is tesseract installed on your system? Error: {e}")
        return "Image with no readable text."

def extract_text(file_path: Path, max_chars: int = 2000) -> str:
    """Extracts text from a file (up to max_chars) for LLM analysis."""
    text = ""
    try:
        if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.heic']:
            text = extract_text_from_image(file_path)
        elif file_path.suffix.lower() == '.pdf':
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text += page.extract_text() + " "
                    if len(text) > max_chars:
                        break
            except ImportError:
                logging.warning("PyPDF2 not installed. Cannot read PDF.")
        else:
            # Attempt to read as raw text
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read(max_chars)
    except Exception as e:
        logging.error(f"Error extracting text from {file_path}: {e}")
    
    return text[:max_chars].strip()

class LocalLLM:
    """
    Interfaces with the local Ollama instance or TF-IDF for Semantic Categorization and Smart Renaming.
    """
    def __init__(self, model: str = "llama3.2", use_ollama: bool = False):
        self.model = model
        self.use_ollama = use_ollama

    def extract_keywords(self, text: str) -> str:
        """Uses TF-IDF to extract top 3 keywords from text."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            import re
            
            clean_text = re.sub(r'[^a-zA-Z\s]', '', text).lower()
            if not clean_text.strip():
                return ""
                
            vectorizer = TfidfVectorizer(stop_words='english', max_features=10)
            tfidf = vectorizer.fit_transform([clean_text])
            
            importance = zip(vectorizer.get_feature_names_out(), tfidf.toarray()[0])
            sorted_words = sorted(importance, key=lambda x: x[1], reverse=True)
            top_words = [w[0].capitalize() for w in sorted_words[:3]]
            
            if not top_words:
                return ""
                
            return "_".join(top_words)
        except Exception as e:
            logging.error(f"Keyword extraction failed: {e}")
            return ""

    def analyze_and_rename(self, file_path: Path, categories: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Reads the file content and asks the LLM for:
        1. The best category from the categories list.
        2. A clean, descriptive filename.
        Returns (category, new_filename)
        """
        text = extract_text(file_path)
        if not text:
            return None, None
            
        if not self.use_ollama:
            # Option 1: Fast, shippable Keyword Extraction
            keywords = self.extract_keywords(text)
            new_name = None
            if keywords:
                new_name = sanitize_filename(f"{keywords}{file_path.suffix}", file_path.suffix)
            return None, new_name

        # Option 2: Ollama LLM
        prompt = f"""
        You are an expert file organizer. Analyze the following text (which is either extracted document content or an AI-generated description of a photo) and provide two things:
        1. The category this file belongs to, chosen STRICTLY from this exact list: {categories}. If unsure, pick the closest one.
        2. A logical, professional filename using underscores. 
           - If it is a document, receipt, or invoice, use a formal document title (e.g., 'HomeDepot_Receipt.pdf', 'Financial_Report.docx'). 
           - If it is just a regular photo or picture, describe the visual subject concisely (e.g., 'Photo_of_Shorts.png', 'Desktop_Screenshot.jpg').
           DO NOT summarize long stories. The filename MUST be 5 words or less. Retain the original extension {file_path.suffix}.

        File Content/Description:
        {text}

        Respond ONLY with a valid JSON object in this exact format, with no other text:
        {{"category": "CategoryName", "filename": "short_clean_name.ext"}}
        """
        
        try:
            response = ollama.chat(model=self.model, messages=[{'role': 'user', 'content': prompt}], format='json')
            content = response['message']['content']
            data = json.loads(content)
            
            category = data.get("category")
            new_name = data.get("filename")
            
            if new_name:
                new_name = sanitize_filename(new_name, file_path.suffix)
            
            # Validation
            if category not in categories:
                category = None
            
            return category, new_name
            
        except Exception as e:
            logging.error(f"LLM processing failed for {file_path.name}: {e}")
            return None, None
