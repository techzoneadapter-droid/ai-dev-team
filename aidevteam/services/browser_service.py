from __future__ import annotations

import os
import subprocess
from pathlib import Path


def detect_default_browser_candidates() -> list[str]:
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
    ]
    return [p for p in candidates if p and Path(p).exists()]


def open_profile(browser_exe: str, profile_dir: str, url: str) -> None:
    exe = Path(browser_exe)
    if not exe.exists():
        raise FileNotFoundError(f"Browser executable not found: {browser_exe}")

    args = [str(exe)]
    if profile_dir.strip():
        args.append(f"--profile-directory={profile_dir.strip()}")
    args.extend(["--new-window", url.strip() or "https://chatgpt.com/"])
    subprocess.Popen(args, close_fds=True)
