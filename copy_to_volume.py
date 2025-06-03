import shutil
import os

def copy_files_to_volume():
    print("🔥 JSON хуулалт эхэллээ")
    # Railway дотор GitHub repo-гийн root зам
    LOCAL_PATH = "/app"
    VOLUME_PATH = "/mnt/data"

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
