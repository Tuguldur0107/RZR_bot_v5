import shutil
import os

# Локал дээрх зам — JSON файлууд чинь байгаа газар
LOCAL_PATH = "D:/BotRZR/GITHUB/RZR_bot_v5"

# Railway Volume зам — bot дотор үүссэн volume
VOLUME_PATH = "/mnt/data"

# Хуулах файлуудын нэрс
json_files = [
    "scores.json",
    "match_log.json",
    "last_match.json",
    "donate_shields.json",
    "donator.json",
    "score_log.jsonl"
]

for file in json_files:
    src = os.path.join(LOCAL_PATH, file)
    dest = os.path.join(VOLUME_PATH, file)
    
    try:
        shutil.copyfile(src, dest)
        print(f"✅ {file} → /mnt/data руу хууллаа.")
    except Exception as e:
        print(f"❌ {file} хуулж чадсангүй: {e}")
