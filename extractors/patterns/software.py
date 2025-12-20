"""Software URL patterns for identifying code repositories and package registries."""

import re

# Package registries (high confidence - always software)
PACKAGE_REGISTRY_PATTERNS = {
    "pypi": re.compile(
        r"(?:https?://)?pypi\.org/project/([a-zA-Z0-9_-]+)",
        re.IGNORECASE
    ),
    "cran": re.compile(
        r"(?:https?://)?cran\.r-project\.org/package=([a-zA-Z0-9_.]+)",
        re.IGNORECASE
    ),
    "npm": re.compile(
        r"(?:https?://)?(?:www\.)?npmjs\.com/package/([a-zA-Z0-9@/._-]+)",
        re.IGNORECASE
    ),
    "conda": re.compile(
        r"(?:https?://)?anaconda\.org/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)",
        re.IGNORECASE
    ),
    "rubygems": re.compile(
        r"(?:https?://)?rubygems\.org/gems/([a-zA-Z0-9_-]+)",
        re.IGNORECASE
    ),
    "cargo": re.compile(
        r"(?:https?://)?crates\.io/crates/([a-zA-Z0-9_-]+)",
        re.IGNORECASE
    ),
    "packagist": re.compile(
        r"(?:https?://)?packagist\.org/packages/([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)",
        re.IGNORECASE
    ),
    "bioconductor": re.compile(
        r"(?:https?://)?bioconductor\.org/packages/([a-zA-Z0-9_.]+)",
        re.IGNORECASE
    ),
}

# Code repository patterns
CODE_REPO_PATTERNS = {
    "github": re.compile(
        r"(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)(?:/[^\s)\"'<>]*)?",
        re.IGNORECASE
    ),
    "gitlab": re.compile(
        r"(?:https?://)?(?:www\.)?gitlab\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)(?:/[^\s)\"'<>]*)?",
        re.IGNORECASE
    ),
    "bitbucket": re.compile(
        r"(?:https?://)?(?:www\.)?bitbucket\.org/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)(?:/[^\s)\"'<>]*)?",
        re.IGNORECASE
    ),
    "sourceforge": re.compile(
        r"(?:https?://)?(?:www\.)?sourceforge\.net/projects/([a-zA-Z0-9_-]+)",
        re.IGNORECASE
    ),
    "codeberg": re.compile(
        r"(?:https?://)?codeberg\.org/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)(?:/[^\s)\"'<>]*)?",
        re.IGNORECASE
    ),
}

# Software archive patterns
SOFTWARE_ARCHIVE_PATTERNS = {
    "software_heritage": re.compile(
        r"(?:https?://)?archive\.softwareheritage\.org/([^\s)\"'<>]+)",
        re.IGNORECASE
    ),
    "codeocean": re.compile(
        r"(?:https?://)?codeocean\.com/capsule/([a-zA-Z0-9_-]+)",
        re.IGNORECASE
    ),
    "zenodo": re.compile(
        r"(?:https?://)?zenodo\.org/record/([0-9]+)",
        re.IGNORECASE
    ),
}

# Paths to exclude from code repositories (non-code pages)
EXCLUDED_PATHS = [
    "/wiki", "/issues", "/pull", "/pulls", "/discussions",
    "/projects", "/actions", "/security", "/pulse", "/graphs",
    "/settings", "/stargazers", "/watchers", "/network", "/forks",
]

# File extensions that indicate data/documentation (not code)
DATA_EXTENSIONS = [
    ".csv", ".json", ".xml", ".xlsx", ".xls", ".tsv", ".dat",
    ".txt", ".md", ".rst", ".pdf", ".doc", ".docx",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp",
    ".zip", ".tar", ".gz", ".tar.gz", ".rar", ".7z",
]

# GitHub Pages pattern (not a repo)
GITHUB_PAGES_PATTERN = re.compile(
    r"(?:https?://)?([a-zA-Z0-9_-]+)\.github\.io/",
    re.IGNORECASE
)


def is_excluded_path(url: str) -> bool:
    """Check if URL path should be excluded (wiki, issues, etc.).

    Args:
        url: The URL to check.

    Returns:
        True if the URL should be excluded.
    """
    url_lower = url.lower()

    # Check excluded path patterns as path segments
    for excluded in EXCLUDED_PATHS:
        if excluded in url_lower:
            return True

    # Check for blob/raw paths with data extensions
    if "/blob/" in url_lower or "/raw/" in url_lower:
        for ext in DATA_EXTENSIONS:
            if url_lower.endswith(ext):
                return True

    return False


def is_github_pages(url: str) -> bool:
    """Check if URL is a GitHub Pages site."""
    return bool(GITHUB_PAGES_PATTERN.match(url))


def is_software_url(url: str) -> bool:
    """Check if a URL matches any known software platform pattern.

    Args:
        url: The URL to check.

    Returns:
        True if the URL is a recognized software URL.
    """
    if not url:
        return False

    if is_github_pages(url):
        return False

    if is_excluded_path(url):
        return False

    for pattern in PACKAGE_REGISTRY_PATTERNS.values():
        if pattern.search(url):
            return True

    for pattern in CODE_REPO_PATTERNS.values():
        if pattern.search(url):
            return True

    for pattern in SOFTWARE_ARCHIVE_PATTERNS.values():
        if pattern.search(url):
            return True

    return False
