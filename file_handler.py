"""
Kiyomi Universal File Handler - Handle any file type seamlessly

Features:
- Detect file type and handle appropriately
- Extract text from PDFs
- Parse documents (docx, etc.)
- Handle code files
- Process images with vision
"""
import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import subprocess

from config import BASE_DIR

logger = logging.getLogger(__name__)

# File handling configuration
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# Supported file types and handlers
FILE_HANDLERS = {
    "image": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"],
    "document": [".pdf", ".docx", ".doc", ".rtf", ".odt"],
    "spreadsheet": [".xlsx", ".xls", ".csv"],
    "code": [".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".yaml", ".yml", ".md", ".txt"],
    "archive": [".zip", ".tar", ".gz", ".rar"],
    "audio": [".mp3", ".wav", ".ogg", ".m4a"],
    "video": [".mp4", ".mov", ".avi", ".webm"],
}


def detect_file_type(file_path: Path) -> str:
    """Detect the type category of a file."""
    suffix = file_path.suffix.lower()

    for file_type, extensions in FILE_HANDLERS.items():
        if suffix in extensions:
            return file_type

    # Use mimetypes as fallback
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("text/"):
            return "code"
        if mime_type.startswith("audio/"):
            return "audio"
        if mime_type.startswith("video/"):
            return "video"

    return "unknown"


async def extract_text_from_pdf(pdf_path: Path) -> Tuple[bool, str]:
    """Extract text from a PDF file."""
    try:
        # Try using pdftotext (poppler)
        result = await asyncio.create_subprocess_exec(
            "pdftotext", str(pdf_path), "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode == 0:
            return True, stdout.decode("utf-8", errors="replace")

        # Try PyPDF2 as fallback
        try:
            import PyPDF2
            text = []
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text.append(page.extract_text())
            return True, "\n\n".join(text)
        except ImportError:
            pass

        return False, "PDF extraction tools not available"

    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return False, str(e)


async def extract_text_from_docx(docx_path: Path) -> Tuple[bool, str]:
    """Extract text from a Word document."""
    try:
        import docx
        doc = docx.Document(docx_path)
        text = "\n\n".join([para.text for para in doc.paragraphs])
        return True, text
    except ImportError:
        # Try using textutil on macOS
        try:
            result = await asyncio.create_subprocess_exec(
                "textutil", "-convert", "txt", "-stdout", str(docx_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            if result.returncode == 0:
                return True, stdout.decode("utf-8", errors="replace")
        except:
            pass
        return False, "DOCX extraction not available (install python-docx)"
    except Exception as e:
        return False, str(e)


async def read_code_file(file_path: Path) -> Tuple[bool, str]:
    """Read a code/text file with syntax info."""
    try:
        content = file_path.read_text(errors="replace")
        extension = file_path.suffix

        # Add language hint
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".jsx": "jsx",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
        }

        lang = lang_map.get(extension, "")

        return True, f"```{lang}\n{content}\n```"

    except Exception as e:
        return False, str(e)


async def parse_csv(csv_path: Path) -> Tuple[bool, str]:
    """Parse a CSV file and return a summary."""
    try:
        import csv
        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            return True, "Empty CSV file"

        headers = rows[0]
        data_rows = rows[1:20]  # First 20 data rows

        # Format as table
        result = f"**CSV File: {csv_path.name}**\n"
        result += f"Columns: {len(headers)}, Rows: {len(rows)-1}\n\n"
        result += "| " + " | ".join(headers) + " |\n"
        result += "| " + " | ".join(["---"] * len(headers)) + " |\n"

        for row in data_rows:
            result += "| " + " | ".join(row[:len(headers)]) + " |\n"

        if len(rows) > 21:
            result += f"\n... and {len(rows) - 21} more rows"

        return True, result

    except Exception as e:
        return False, str(e)


async def process_file(
    file_path: Path,
    caption: Optional[str] = None
) -> Tuple[str, str, Optional[Dict]]:
    """
    Process a file and return handling info.

    Returns:
        (file_type, extracted_content, metadata)
    """
    file_type = detect_file_type(file_path)
    content = ""
    metadata = {"original_name": file_path.name, "size": file_path.stat().st_size}

    if file_type == "image":
        # Images are handled by vision - return path
        content = f"Image file saved at: {file_path}"
        metadata["needs_vision"] = True

    elif file_type == "document":
        if file_path.suffix.lower() == ".pdf":
            success, text = await extract_text_from_pdf(file_path)
            content = text if success else f"Could not extract PDF: {text}"
        elif file_path.suffix.lower() in [".docx", ".doc"]:
            success, text = await extract_text_from_docx(file_path)
            content = text if success else f"Could not extract document: {text}"
        else:
            content = f"Document file: {file_path.name}"

    elif file_type == "spreadsheet":
        if file_path.suffix.lower() == ".csv":
            success, text = await parse_csv(file_path)
            content = text if success else f"Could not parse CSV: {text}"
        else:
            content = f"Spreadsheet file: {file_path.name}"
            metadata["note"] = "Excel files need special handling"

    elif file_type == "code":
        success, text = await read_code_file(file_path)
        content = text if success else f"Could not read file: {text}"

    elif file_type == "audio":
        content = f"Audio file saved at: {file_path}"
        metadata["needs_transcription"] = True

    elif file_type == "archive":
        content = f"Archive file: {file_path.name}"
        metadata["can_extract"] = True

    else:
        content = f"File saved at: {file_path}"

    return file_type, content, metadata


def build_file_prompt(
    file_type: str,
    content: str,
    metadata: Dict,
    user_caption: Optional[str] = None
) -> str:
    """Build a prompt for Claude to handle a file."""
    prompt_parts = [f"Richard sent a file: {metadata.get('original_name', 'unknown')}"]

    if user_caption:
        prompt_parts.append(f"His message: \"{user_caption}\"")

    if metadata.get("needs_vision"):
        prompt_parts.append(f"\nThe image is at: {content}")
        prompt_parts.append("Analyze this image and help with whatever Richard needs.")

    elif metadata.get("needs_transcription"):
        prompt_parts.append(f"\nThis is an audio file at: {content}")
        prompt_parts.append("Transcribe this and respond to whatever was said.")

    else:
        prompt_parts.append(f"\nFile contents:\n{content[:5000]}")
        if len(content) > 5000:
            prompt_parts.append("... (content truncated)")

    if not user_caption:
        prompt_parts.append("\nHelp Richard with this file. If it's code, review it. If it's a document, summarize it.")

    return "\n\n".join(prompt_parts)


async def handle_file_upload(
    file_path: Path,
    caption: Optional[str] = None,
    execute_fn=None
) -> Tuple[bool, str]:
    """
    Full file upload handling workflow.

    Returns (success, response)
    """
    try:
        # Process the file
        file_type, content, metadata = await process_file(file_path, caption)

        # Build prompt
        prompt = build_file_prompt(file_type, content, metadata, caption)

        # Execute via Claude if function provided
        if execute_fn:
            result, success = await execute_fn(prompt)
            return success, result
        else:
            return True, f"File processed:\n\nType: {file_type}\n\n{content[:1000]}"

    except Exception as e:
        logger.error(f"File handling error: {e}")
        return False, f"Error processing file: {e}"
