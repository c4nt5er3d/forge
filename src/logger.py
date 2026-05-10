import logging
from pathlib import Path
from datetime import datetime

def setup_logging() -> None:
    """
    Configures the application's logging mechanism.
    
    Sets up a file handler to store logs in the `logs/` directory
    without outputting to the terminal, allowing Rich to handle the UI.
    """
    log_dir: Path = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    timestamp: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file: Path = log_dir / f"organizer_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file)
        ]
    )
    logging.info(f"Log file initialized at {log_file}")
