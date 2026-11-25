# updates.py
import sys
import subprocess
import json
from typing import List, Tuple

from .constants import REQUIRED_PACKAGES

def check_pip_updates() -> List[Tuple[str, str, str]]:
    outdated = []
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
                                capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            for pkg in data:
                if pkg['name'] in REQUIRED_PACKAGES:
                    outdated.append((pkg['name'], pkg['version'], pkg['latest_version']))
    except Exception as e:
        print(f"Проверка обновлений не удалась: {e}")
    return outdated

def notify_updates() -> None:
    outdated = check_pip_updates()
    if outdated:
        print("\n⚠️ Доступны обновления библиотек:")
        for pkg, cur, latest in outdated:
            print(f"   {pkg}: {cur} -> {latest}")
        print("   Выполните: pip install --upgrade " + " ".join([p[0] for p in outdated]))
    else:
        print("✅ Все библиотеки актуальны.")