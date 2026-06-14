import json
import os

DATA_FILE = "../user_data.json"


def save_user_data(user_states: dict):
    to_save = {str(k): v for k, v in user_states.items()}
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)


def load_user_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {int(k): v for k, v in data.items()}
    return {}