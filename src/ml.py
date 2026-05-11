import os
import re
import joblib
import logging
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
except ImportError:
    logging.warning("scikit-learn is not installed. ML features will be disabled.")
    Pipeline = None

from rich.console import Console

console = Console()

class MLClassifier:
    """
    Traditional Machine Learning Classifier for file categorization.
    Uses TF-IDF Vectorization and Naive Bayes to classify files based on their names.
    """
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path(__file__).parent.parent / "models" / "classifier.joblib"
        self.pipeline = None
        self._load_model()

    def _load_model(self) -> None:
        """Loads the pre-trained model from disk if it exists."""
        if self.model_path.exists() and Pipeline is not None:
            try:
                self.pipeline = joblib.load(self.model_path)
            except Exception as e:
                logging.error(f"Failed to load ML model: {e}")
        
    def _clean_filename(self, filename: str) -> str:
        """
        Cleans the filename by removing the extension and non-alphabetic characters.
        This provides a clean string of words for TF-IDF.
        """
        name = os.path.splitext(filename)[0]
        # Replace special characters and numbers with spaces
        name = re.sub(r'[^a-zA-Z]', ' ', name)
        # Convert to lowercase and strip extra spaces
        return ' '.join(name.lower().split())

    def extract_features(self, file_path: Path, use_content: bool = False) -> str:
        """
        Extracts features (clean filename + extension + optional content) as a single document string.
        """
        clean_name = self._clean_filename(file_path.name)
        ext = file_path.suffix.lower().replace('.', '')
        base = f"{clean_name} {ext}"
        
        if use_content:
            try:
                from src.llm import extract_text
                content = extract_text(file_path, max_chars=500)
                content_clean = re.sub(r'[^a-zA-Z\s]', ' ', content).lower()
                base = f"{base} {content_clean}"
            except Exception:
                pass  # Graceful degradation — filename features still used
        return base

    def train(self, data_dir: Path) -> None:
        """
        Trains the ML model using an already organized directory.
        Folder names are treated as labels.
        """
        if Pipeline is None:
            console.print("  [bold red]Error:[/bold red] scikit-learn is required for training.")
            return

        if not data_dir.exists() or not data_dir.is_dir():
            console.print(f"  [bold red]Training error:[/bold red] [red]{data_dir} is not a valid directory.[/red]")
            return

        console.print(f"  [#e8550a]›[/#e8550a] [#888888]scanning for data:[/#888888] [#ffffff]{data_dir}[/#ffffff]")
        
        texts: List[str] = []
        labels: List[str] = []

        # Assuming subfolders are the category labels
        for category_folder in data_dir.iterdir():
            if category_folder.is_dir() and not category_folder.name.startswith("."):
                category = category_folder.name
                for file_path in category_folder.rglob("*"):
                    if file_path.is_file() and not file_path.name.startswith("."):
                        texts.append(self.extract_features(file_path, use_content=True))
                        labels.append(category)

        if not texts:
            console.print("  [yellow]No training data found in the provided directory.[/yellow]")
            return

        console.print(f"  [#e8550a]›[/#e8550a] [#28c840]Found {len(texts)} files[/#28c840] across [#ffffff]{len(set(labels))}[/#ffffff] categories.")
        console.print("  [#e8550a]›[/#e8550a] [#5bc8f5]Training TF-IDF Vectorizer & MultinomialNB Model...[/#5bc8f5]")

        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(max_features=5000, stop_words='english')),
            ('clf', MultinomialNB())
        ])

        self.pipeline.fit(texts, labels)

        # Save the trained model
        self.model_path.parent.mkdir(exist_ok=True)
        joblib.dump(self.pipeline, self.model_path)
        console.print(f"\n  [#28c840]✔ Model trained and saved to:[/#28c840] [#ffffff]{self.model_path}[/#ffffff]\n")

    def predict(self, file_path: Path) -> Tuple[Optional[str], float]:
        """
        Predicts the category of a given file and returns the confidence score.
        """
        if self.pipeline is None:
            return None, 0.0
        
        features = self.extract_features(file_path, use_content=True)
        try:
            if hasattr(self.pipeline, "predict_proba"):
                probs = self.pipeline.predict_proba([features])[0]
                max_prob = max(probs)
                best_class = self.pipeline.classes_[probs.argmax()]
                return best_class, float(max_prob)
            else:
                prediction = self.pipeline.predict([features])[0]
                return prediction, 1.0
        except Exception as e:
            logging.error(f"Prediction error for {file_path.name}: {e}")
            return None, 0.0
