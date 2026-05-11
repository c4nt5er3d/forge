import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, List

def validate_categories(categories: Any) -> None:
    # Ensures the categories JSON is a flat dictionary of lists.
    # This prevents the classifier from encountering malformed data types during matching.
    if not isinstance(categories, dict):
        raise ValueError("Categories must be a JSON object (dictionary).")
    for category, extensions in categories.items():
        if not isinstance(extensions, list):
            raise ValueError(f"Category '{category}' must have a list of extensions.")
        for ext in extensions:
            if not isinstance(ext, str):
                raise ValueError(f"Extension '{ext}' in category '{category}' must be a string.")

def load_categories(config_path: Path = None) -> Dict[str, List[str]]:
    # Loads the extension-to-category mapping.
    # We default to an empty dict if the file is missing to allow for pure ML categorization.
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "categories.json"
    try:
        with open(config_path, "r") as f:
            categories: Dict[str, List[str]] = json.load(f)
        validate_categories(categories)
        return categories
    except FileNotFoundError:
        logging.warning(f"Categories file not found at {config_path}. Using default empty categories.")
        return {}
    except Exception as e:
        logging.error(f"Error loading categories: {e}")
        sys.exit(1)

def validate_config(config: Any) -> None:
    # Validates general application settings.
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object.")

def load_config(env: str = "default") -> Dict[str, Any]:
    # Resolves configuration by layering environment-specific files over defaults.
    # This enables easy switching between 'test' and 'default' modes for integration testing.
    config_dir: Path = Path(__file__).parent.parent / "config"
    env_config_path: Path = config_dir / f"config.{env}.json"
    default_config_path: Path = config_dir / "config.json"
    
    config_path: Path = env_config_path if env_config_path.exists() else default_config_path
    
    config: Dict[str, Any] = {
        "default_target": ".",
        "default_destination": None,
        "copy_mode": False,
        "date_sort": False,
        "exclude": [],
        "categories_file": str(config_dir / "categories.json")
    }
    
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                user_config: Dict[str, Any] = json.load(f)
            validate_config(user_config)
            config.update(user_config)
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            sys.exit(1)
            
    return config

def load_all_configs(env: str = "default") -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
    # Unified loader that provides a consistent snapshot of both 
    # system settings and categorization rules.
    config: Dict[str, Any] = load_config(env)
    validate_config(config)
    categories_path: Path = Path(config.get("categories_file", Path(__file__).parent.parent / "config" / "categories.json"))
    categories: Dict[str, List[str]] = load_categories(categories_path)
    validate_categories(categories)
    return config, categories
