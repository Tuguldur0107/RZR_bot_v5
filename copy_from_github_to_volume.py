import shutil
import os

def copy_files_from_app_to_volume():
    print("🚚 GitHub-аас Render volume руу JSON хуулж байна...")

    LOCAL_PATH = "/opt/render/project/src"
    VOLUME_PATH = "/render_disks/rzr-disk"

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
            print(f"✅ {file} → Render volume руу хууллаа.")
        except Exception as e:
            print(f"❌ {file} хуулж чадсангүй: {e}")
    print("📁 JSON exists:", os.path.exists("/opt/render/project/src/scores.json"))

