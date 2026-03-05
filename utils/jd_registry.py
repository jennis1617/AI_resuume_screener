import json
import os
from datetime import datetime

REGISTRY_FILE = "jd_registry.json"


def _load_registry():
    if not os.path.exists(REGISTRY_FILE):
        return {}
    with open(REGISTRY_FILE, "r") as f:
        return json.load(f)


def _save_registry(data):
    with open(REGISTRY_FILE, "w") as f:
        json.dump(data, f, indent=4)


def add_jd_entry(username, jd_name, sharepoint_path):
    data = _load_registry()

    if username not in data:
        data[username] = []

    data[username].append({
        "jd_name": jd_name,
        "sharepoint_path": sharepoint_path,
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    _save_registry(data)


def get_user_jds(username):
    data = _load_registry()
    return data.get(username, [])