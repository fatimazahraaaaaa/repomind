"""
RepoMind Repository Handler
Handles cloning and analyzing GitHub repositories
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import git
from git.exc import GitCommandError


# Configuration constants
MAX_FILES = 50
MAX_FILE_SIZE = 100 * 1024  # 100KB
CLONE_TIMEOUT = 60  # seconds

# Directories to skip during file tree walking
EXCLUDED_DIRS = {
    '.git', 'node_modules', '__pycache__', 'venv', 'env', '.venv',
    'dist', 'build', '.next', '.cache', 'coverage', '.pytest_cache',
    '.tox', '.eggs', '*.egg-info', 'htmlcov', '.mypy_cache',
    '.ruff_cache', 'target', 'bin', 'obj', '.gradle'
}

# File patterns to skip
EXCLUDED_FILES = {
    '.env', '.env.local', '.env.development', '.env.production',
    '.DS_Store', 'Thumbs.db', '*.pyc', '*.pyo', '*.so', '*.dll',
    '*.exe', '*.bin', '*.lock', 'package-lock.json', 'yarn.lock',
    'poetry.lock', 'Pipfile.lock', '*.min.js', '*.min.css'
}

# Priority files (lower number = higher priority)
PRIORITY_FILES = {
    # Tier 0: Critical documentation and entry points
    'readme.md': 0, 'readme.rst': 0, 'readme.txt': 0, 'readme': 0,
    'license': 0, 'license.md': 0, 'license.txt': 0,
    'contributing.md': 0, 'contributing': 0,
    'main.py': 0, 'app.py': 0, '__init__.py': 0,
    'index.js': 0, 'index.ts': 0, 'server.js': 0, 'server.ts': 0,
    'main.go': 0, 'main.java': 0, 'program.cs': 0,
    
    # Tier 1: Configuration files
    'package.json': 1, 'tsconfig.json': 1, 'jsconfig.json': 1,
    'requirements.txt': 1, 'setup.py': 1, 'pyproject.toml': 1,
    'cargo.toml': 1, 'go.mod': 1, 'pom.xml': 1, 'build.gradle': 1,
    'dockerfile': 1, 'docker-compose.yml': 1, 'docker-compose.yaml': 1,
    '.gitignore': 1, '.dockerignore': 1,
    'makefile': 1, 'cmake.txt': 1,
    'config.json': 1, 'config.yaml': 1, 'config.yml': 1,
    'settings.py': 1, 'settings.json': 1,
}

# Source code extensions (Tier 2)
SOURCE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
    '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php', '.swift',
    '.kt', '.scala', '.r', '.m', '.sh', '.bash', '.sql', '.vue'
}

# Documentation extensions (Tier 3)
DOC_EXTENSIONS = {
    '.md', '.rst', '.txt', '.adoc', '.tex'
}


def _should_skip_directory(dirname: str) -> bool:
    """Check if directory should be skipped during traversal."""
    dirname_lower = dirname.lower()
    return any(
        dirname_lower == excluded.lower() or 
        dirname_lower.startswith('.') and dirname != '.github'
        for excluded in EXCLUDED_DIRS
    )


def _should_skip_file(filename: str) -> bool:
    """Check if file should be skipped."""
    filename_lower = filename.lower()
    
    # Check exact matches
    if filename_lower in {f.lower() for f in EXCLUDED_FILES if not f.startswith('*')}:
        return True
    
    # Check pattern matches
    for pattern in EXCLUDED_FILES:
        if pattern.startswith('*'):
            ext = pattern[1:]  # Remove the *
            if filename_lower.endswith(ext):
                return True
    
    return False


def _get_file_priority(filepath: str) -> int:
    """
    Calculate priority score for a file (lower = higher priority).
    Returns: 0 (critical), 1 (config), 2 (source), 3 (docs), 4 (other)
    """
    filename = os.path.basename(filepath).lower()
    ext = os.path.splitext(filename)[1].lower()
    
    # Check priority files
    if filename in PRIORITY_FILES:
        return PRIORITY_FILES[filename]
    
    # Check if in src/ or root directory
    path_parts = Path(filepath).parts
    in_src = len(path_parts) <= 2 or 'src' in path_parts[:2]
    
    # Source code files
    if ext in SOURCE_EXTENSIONS:
        return 2 if in_src else 3
    
    # Documentation files
    if ext in DOC_EXTENSIONS:
        return 3
    
    # Everything else
    return 4


def _is_text_file(filepath: str) -> bool:
    """
    Check if file is likely a text file.
    Uses extension-based heuristic for performance.
    """
    text_extensions = SOURCE_EXTENSIONS | DOC_EXTENSIONS | {
        '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg',
        '.conf', '.properties', '.env', '.gitignore', '.dockerignore',
        '.html', '.css', '.scss', '.sass', '.less', '.svg'
    }
    
    ext = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath).lower()
    
    # Check extension
    if ext in text_extensions:
        return True
    
    # Check filename (files without extensions)
    if not ext and filename in {'makefile', 'dockerfile', 'license', 'readme', 'contributing'}:
        return True
    
    return False


def _read_file_safely(filepath: str, max_size: int = MAX_FILE_SIZE) -> Optional[str]:
    """
    Safely read file content with error handling.
    Returns None if file cannot be read or is too large.
    """
    try:
        # Check file size
        if os.path.getsize(filepath) > max_size:
            return None
        
        # Try UTF-8 first
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Fallback to latin-1 (never fails)
            with open(filepath, 'r', encoding='latin-1') as f:
                return f.read()
                
    except (OSError, PermissionError, FileNotFoundError):
        return None


def _collect_files(repo_path: str) -> List[Tuple[str, int]]:
    """
    Walk the repository and collect all relevant files with priorities.
    Returns list of (relative_path, priority) tuples.
    """
    files_with_priority = []
    
    for root, dirs, files in os.walk(repo_path):
        # Filter out excluded directories (modify in-place)
        dirs[:] = [d for d in dirs if not _should_skip_directory(d)]
        
        for filename in files:
            # Skip excluded files
            if _should_skip_file(filename):
                continue
            
            # Get full and relative paths
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, repo_path)
            
            # Skip if not a text file
            if not _is_text_file(full_path):
                continue
            
            # Calculate priority
            priority = _get_file_priority(rel_path)
            files_with_priority.append((rel_path, priority))
    
    return files_with_priority


def fetch_repo(github_url: str) -> Dict:
    """
    Clone a GitHub repository and extract its file structure and contents.
    
    Args:
        github_url: GitHub repository URL (https://github.com/user/repo)
    
    Returns:
        Dictionary with:
        - file_tree: List of all file paths in the repository
        - file_contents: Dictionary mapping file paths to their contents (up to 50 files)
        - error: Error message if something went wrong, None otherwise
    
    Example:
        >>> result = fetch_repo("https://github.com/user/repo")
        >>> print(result['file_tree'])
        ['README.md', 'src/main.py', 'requirements.txt', ...]
        >>> print(result['file_contents']['README.md'])
        '# My Project...'
    """
    temp_dir = None
    
    try:
        # Validate URL
        if not github_url or not isinstance(github_url, str):
            return {
                "file_tree": [],
                "file_contents": {},
                "error": "Invalid GitHub URL provided"
            }
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix='repomind_')
        
        # Clone repository
        try:
            repo = git.Repo.clone_from(
                github_url,
                temp_dir,
                depth=1,  # Shallow clone for speed
                single_branch=True
            )
        except GitCommandError as e:
            error_msg = str(e)
            if "not found" in error_msg.lower() or "repository not found" in error_msg.lower():
                return {
                    "file_tree": [],
                    "file_contents": {},
                    "error": f"Repository not found: {github_url}"
                }
            elif "authentication" in error_msg.lower() or "permission" in error_msg.lower():
                return {
                    "file_tree": [],
                    "file_contents": {},
                    "error": "Authentication failed. Repository may be private."
                }
            else:
                return {
                    "file_tree": [],
                    "file_contents": {},
                    "error": f"Failed to clone repository: {error_msg}"
                }
        
        # Collect all files with priorities
        files_with_priority = _collect_files(temp_dir)
        
        # Sort by priority (lower number first), then alphabetically
        files_with_priority.sort(key=lambda x: (x[1], x[0]))
        
        # Extract file tree (all files)
        file_tree = [path for path, _ in files_with_priority]
        
        # Read contents of top priority files (up to MAX_FILES)
        file_contents = {}
        files_read = 0
        
        for rel_path, priority in files_with_priority:
            if files_read >= MAX_FILES:
                break
            
            full_path = os.path.join(temp_dir, rel_path)
            content = _read_file_safely(full_path)
            
            if content is not None:
                # Normalize path separators to forward slashes
                normalized_path = rel_path.replace(os.sep, '/')
                file_contents[normalized_path] = content
                files_read += 1
        
        return {
            "file_tree": [p.replace(os.sep, '/') for p in file_tree],
            "file_contents": file_contents,
            "error": None
        }
    
    except Exception as e:
        return {
            "file_tree": [],
            "file_contents": {},
            "error": f"Unexpected error: {str(e)}"
        }
    
    finally:
        # Cleanup temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass  # Best effort cleanup


# Example usage and testing
if __name__ == "__main__":
    # Test with a small public repository
    test_url = "https://github.com/octocat/Hello-World"
    result = fetch_repo(test_url)
    
    print(f"Error: {result['error']}")
    print(f"Files found: {len(result['file_tree'])}")
    print(f"Files read: {len(result['file_contents'])}")
    print(f"\nFile tree (first 10):")
    for path in result['file_tree'][:10]:
        print(f"  - {path}")
    print(f"\nFile contents keys (first 5):")
    for path in list(result['file_contents'].keys())[:5]:
        print(f"  - {path} ({len(result['file_contents'][path])} chars)")

# Made with Bob
