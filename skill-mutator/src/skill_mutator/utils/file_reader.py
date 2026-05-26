"""Utilities for reading folders/files and formatting them for an LLM prompt."""

import os
from pathlib import Path


# Supported file extensions mapped to a language label.
SUPPORTED_EXTENSIONS = {
    # Markdown / documents
    ".md": "markdown",
    ".txt": "text",
    ".rst": "rst",
    # Config files
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "cfg",
    ".env": "env",
    # Scripts
    ".py": "python",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".ps1": "powershell",
    ".bat": "batch",
    # Web
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".html": "html",
    ".css": "css",
    # Other code
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".r": "r",
    ".sql": "sql",
    ".dockerfile": "dockerfile",
}

DEFAULT_IGNORE = {
    "__pycache__", ".git", ".svn", "node_modules", ".venv", "venv",
    ".env", "dist", "build", ".pytest_cache", ".mypy_cache",
}


def read_file(file_path: str | Path) -> dict:
    """Read a single file.

    Returns:
        {"path": str, "name": str, "extension": str, "language": str, "content": str}
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {file_path}")
    if not path.is_file():
        raise ValueError(f"not a file: {file_path}")

    extension = path.suffix.lower()
    language = SUPPORTED_EXTENSIONS.get(extension, "text")

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8", errors="replace")
    # Null bytes are valid UTF-8 but break OpenAI JSON payloads — strip them.
    content = content.replace("\x00", "")

    return {
        "path": str(path),
        "name": path.name,
        "extension": extension,
        "language": language,
        "content": content,
    }


def read_folder(
    folder_path: str | Path,
    extensions: list[str] | None = None,
    recursive: bool = True,
    ignore_dirs: set[str] | None = None,
    max_file_size_kb: int = 500,
) -> list[dict]:
    """Read the files inside a folder and return them as a list.

    Args:
        folder_path: folder to read.
        extensions: file extensions to include (None = all of SUPPORTED_EXTENSIONS).
        recursive: whether to descend into subfolders.
        ignore_dirs: set of folder names to skip.
        max_file_size_kb: files larger than this (KB) are skipped.

    Returns:
        A list of file-info dicts (the read_file return shape plus a
        "relative_path" key).
    """
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"folder not found: {folder_path}")
    if not folder.is_dir():
        raise ValueError(f"not a folder: {folder_path}")

    allowed_ext = set(extensions) if extensions else set(SUPPORTED_EXTENSIONS.keys())
    ignore = (ignore_dirs or set()) | DEFAULT_IGNORE
    max_bytes = max_file_size_kb * 1024

    files = []
    pattern = "**/*" if recursive else "*"

    for path in sorted(folder.glob(pattern)):
        # Skip ignored directories.
        if any(part in ignore for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in allowed_ext:
            continue
        if path.stat().st_size > max_bytes:
            continue

        file_info = read_file(path)
        file_info["relative_path"] = str(path.relative_to(folder))
        files.append(file_info)

    return files


def format_files_for_llm(
    files: list[dict],
    include_tree: bool = True,
    max_total_chars: int = 100_000,
) -> str:
    """Format a list of read files into a string suitable for an LLM prompt.

    Args:
        files: results from read_folder / read_file.
        include_tree: whether to include a file-tree summary.
        max_total_chars: max total output chars (large files are truncated to fit).

    Returns:
        The formatted string.
    """
    if not files:
        return "(no files)"

    sections = []

    if include_tree:
        tree_lines = ["## File list\n```"]
        for f in files:
            rel = f.get("relative_path", f["name"])
            size = len(f["content"])
            tree_lines.append(f"  {rel}  ({size:,} chars)")
        tree_lines.append("```\n")
        sections.append("\n".join(tree_lines))

    total_chars = sum(len(f["content"]) for f in files)
    budget = max_total_chars - len("\n".join(sections))

    # When over budget, allocate proportionally across files.
    if total_chars > budget and total_chars > 0:
        ratio = budget / total_chars
    else:
        ratio = 1.0

    for f in files:
        rel = f.get("relative_path", f["name"])
        lang = f["language"]
        content = f["content"]

        # Truncate proportionally.
        allowed = int(len(content) * ratio)
        if allowed < len(content):
            content = content[:allowed] + f"\n... (truncated, {len(f['content']) - allowed:,} chars omitted)"

        sections.append(f"## {rel}\n```{lang}\n{content}\n```")

    return "\n\n".join(sections)


def read_folder_as_prompt(
    folder_path: str | Path,
    system_context: str = "",
    **read_folder_kwargs,
) -> str:
    """Read a folder and return a string ready to use directly as an LLM prompt.

    Args:
        folder_path: folder to read.
        system_context: context description prepended before the file list.
        **read_folder_kwargs: extra arguments forwarded to read_folder.

    Returns:
        A string usable directly as an LLM prompt.
    """
    files = read_folder(folder_path, **read_folder_kwargs)
    formatted = format_files_for_llm(files)

    if system_context:
        return f"{system_context}\n\n{formatted}"
    return formatted
