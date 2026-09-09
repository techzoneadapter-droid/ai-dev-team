from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_CHAT_URL = "https://chatgpt.com/"


def detect_default_browser_candidates() -> list[str]:
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    found: list[str] = []
    for raw in candidates:
        if raw and "%" not in raw and Path(raw).exists() and raw not in found:
            found.append(raw)
    return found


def validate_chat_url(url: str) -> str:
    value = (url or DEFAULT_CHAT_URL).strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Chat URL must be a valid http/https URL")
    return value


def build_launch_command(browser_exe: str, profile_dir: str, url: str) -> list[str]:
    if not browser_exe.strip():
        raise ValueError("Browser executable is not configured")
    exe = Path(browser_exe)
    if not exe.exists():
        raise FileNotFoundError(f"Browser executable not found: {browser_exe}")
    args = [str(exe)]
    if profile_dir.strip():
        args.append(f"--profile-directory={profile_dir.strip()}")
    args.extend(["--new-window", validate_chat_url(url)])
    return args


def open_profile(browser_exe: str, profile_dir: str, url: str) -> None:
    subprocess.Popen(build_launch_command(browser_exe, profile_dir, url), close_fds=True)


def _user_data_dir_for_browser(browser_exe: str) -> Path | None:
    name = Path(browser_exe).name.lower()
    local = Path(os.getenv("LOCALAPPDATA") or "")
    if name == "chrome.exe":
        return local / "Google" / "Chrome" / "User Data"
    if name == "msedge.exe":
        return local / "Microsoft" / "Edge" / "User Data"
    return None


def discover_profiles(browser_exe: str) -> list[tuple[str, str]]:
    """Return (profile directory, display name) without reading cookies/session data."""
    root = _user_data_dir_for_browser(browser_exe)
    if root is None or not root.exists():
        return []
    discovered: dict[str, str] = {}
    local_state = root / "Local State"
    try:
        data = json.loads(local_state.read_text(encoding="utf-8"))
        info_cache = data.get("profile", {}).get("info_cache", {})
        for directory, info in info_cache.items():
            display = str(info.get("name") or directory)
            discovered[directory] = display
    except (OSError, json.JSONDecodeError, TypeError):
        pass

    for child in root.iterdir():
        if child.is_dir() and (child.name == "Default" or child.name.startswith("Profile ")):
            discovered.setdefault(child.name, child.name)
    return sorted(discovered.items(), key=lambda item: (item[0] != "Default", item[0].lower()))
