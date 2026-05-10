import logging
from pathlib import Path
from datetime import datetime

def setup_logging() -> None:
    # Configures a silent file-based logger.
    # We deliberately omit terminal handlers to prevent log noise from 
    # interfering with the Rich-based CLI UI.
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
