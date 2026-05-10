# File Organizer 🗂️

Tidy up your digital chaos with a powerful, configurable file organization script written in Python. This tool automatically sorts files from a target directory into category-based subfolders, making your file system clean and manageable.

##  Features

-   **Automatic Categorization**: Sorts files into logical categories (Images, Documents, Videos, Audio, Archives, etc.) based on their file extensions.
-   **Date-based Sorting**: Optionally organize files into year/month subfolders (e.g., `Images/2023/05-May/photo.jpg`).
-   **Undo/Revert**: Easily undo the last organization run if you change your mind.
-   **Copy Mode**: Copy files instead of moving them for extra safety.
-   **Customizable Categories**: Easily modify or extend categories and file type mappings via a simple JSON configuration file.
-   **Safe by Design**:
    -   **Dry Run Mode**: Preview all proposed changes without moving a single file.
    -   **Collision Handling**: Automatically detects existing filenames and renames duplicates (e.g., `file_1.txt`, `file_2.txt`).
    -   **Transaction Logging**: Every move/copy is recorded, enabling the undo feature.
-   **Flexible Usage**:
    -   Set a target directory explicitly or use the current directory as default.
    -   Optionally specify a separate destination directory for sorted files.
    -   Skip hidden files and subdirectories automatically.

##  Quick Start

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/file_organizer.git
    cd file_organizer
    ```

2.  **Install dependencies:**
    (Optional, as this script uses only the standard library)
    ```bash
    pip install -r requirements.txt
    ```

### Configuration

Customize the file categories by editing the `config/categories.json` file:

```json
{
  "Images": [
    ".jpg",
    ".jpeg",
    ".png",
    ".gif"
  ],
  "Documents": [
    ".pdf",
    ".doc",
    ".docx"
  ],
  "Misc": []
}
```

## ⚙️ Usage

Run the script from the command line. The basic syntax is:

```bash
python src/main.py [OPTIONS]
```

### Options

| Option | Description |
| :--- | :--- |
| `--target <path>` | Specify the directory to organize. Default: current directory (`.`). |
| `--destination <path>` | Specify where sorted folders should be created. Default: same as target. |
| `--dry-run` | Preview the organization without making any changes. |
| `--recursive` | Organize files in subdirectories as well. |
| `--date-sort` | Organize files into Year/Month subfolders within categories. |
| `--copy` | Duplicate files instead of moving them. |
| `--exclude <ext>` | Skip specific file extensions (e.g., `--exclude pdf exe`). |
| `--undo` | Revert the last organization run (restores moved files or deletes copies). |

### Examples

**1. Dry run on the current folder:**
```bash
python src/main.py --dry-run
```

**2. Organize the `Downloads` folder:**
```bash
python src/main.py --target ~/Downloads
```

**3. Organize a folder and move sorted files to a different location:**
```bash
python src/main.py --target ~/Desktop/Unsorted --destination ~/Desktop/Sorted
```

## 📂 Project Structure

```
file_organizer/
├── src/
│   └── main.py               # Main application logic
├── config/
│   └── categories.json       # File type to category mappings
└── README.md                 # Project documentation
```
