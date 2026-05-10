from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

def get_category_by_extension(extension: str, categories: Dict[str, List[str]]) -> str:
    # Deterministic mapping based on the 'categories.json' configuration.
    # Extensions are stored as lower-case to ensure case-insensitive matching.
    for category, extensions in categories.items():
        if extension.lower() in extensions:
            return category
    return "Misc"

# Alias for backward compatibility with the test suite.
get_category = get_category_by_extension

def get_destination_path(file: Path, destination: Path, categories: Dict[str, List[str]], date_sort: bool = False, ml_classifier: Any = None, override_category: Optional[str] = None, dest_name: Optional[str] = None) -> Path:
    # Calculates the final organizational path for a file.
    # It follows a hierarchy: AI Override -> ML Prediction -> Extension Rule.
    category = override_category
    
    if not category:
        if ml_classifier is not None and ml_classifier.pipeline is not None:
            pred, conf = ml_classifier.predict(file)
            
            # Confidence threshold (0.40) is tuned to balance automation with accuracy.
            # If the model is uncertain, we fall back to safe extension-based rules.
            if pred and conf > 0.40:
                category = pred
            else:
                category = get_category_by_extension(file.suffix, categories)
        else:
            category = get_category_by_extension(file.suffix, categories)

    category_folder: Path = destination / category

    if date_sort:
        # We use st_mtime as a proxy for the 'event' date of the file.
        mtime: datetime = datetime.fromtimestamp(file.stat().st_mtime)
        year: str = mtime.strftime("%Y")
        month: str = mtime.strftime("%m-%B")
        category_folder = category_folder / year / month
    
    final_name = dest_name if dest_name else file.name
    return category_folder / final_name
