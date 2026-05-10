from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

def get_category_by_extension(extension: str, categories: Dict[str, List[str]]) -> str:
    """
    Determines the category strictly based on file extension.
    """
    for category, extensions in categories.items():
        if extension.lower() in extensions:
            return category
    return "Misc"

def get_destination_path(file: Path, destination: Path, categories: Dict[str, List[str]], date_sort: bool = False, ml_classifier: Any = None, override_category: Optional[str] = None, dest_name: Optional[str] = None) -> Path:
    """
    Calculates the final destination path for a file using a Hybrid ML + Extension approach.
    """
    category = override_category
    
    # 1. Hybrid ML Approach
    if not category:
        if ml_classifier is not None and ml_classifier.pipeline is not None:
            pred, conf = ml_classifier.predict(file)
            
            # Context-aware sorting: trust ML if confidence is decently high
            if pred and conf > 0.40:
                category = pred
            else:
                category = get_category_by_extension(file.suffix, categories)
        else:
            # Fallback to pure extension rules
            category = get_category_by_extension(file.suffix, categories)

    category_folder: Path = destination / category

    if date_sort:
        mtime: datetime = datetime.fromtimestamp(file.stat().st_mtime)
        year: str = mtime.strftime("%Y")
        month: str = mtime.strftime("%m-%B")
        category_folder = category_folder / year / month
    
    final_name = dest_name if dest_name else file.name
    return category_folder / final_name
