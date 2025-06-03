import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import random
import asyncio
from datetime import datetime, timezone, timedelta
import base64
import requests


BASE_DIR = "/mnt/data"

start = datetime.now(timezone.utc)
end = start + timedelta(hours=5)

elapsed = end - start  # ⏱ timedelta object

SCORE_FILE = f"{BASE_DIR}/scores.json"
LOG_FILE = f"{BASE_DIR}/match_log.json"
LAST_FILE = f"{BASE_DIR}/last_match.json"
SHIELD_FILE = f"{BASE_DIR}/donate_shields.json"
DONATOR_FILE = f"{BASE_DIR}/donator.json"
SCORE_LOG_FILE = f"{BASE_DIR}/score_log.jsonl"

# 🧠 Тоглоомын Session-н төлөв
GAME_SESSION = {
    "active": False,
    "start_time": None,
    "last_win_time": None
}

def load_donators():
    if not os.path.exists(DONATOR_FILE):
        return {}
    try:
        with open(DONATOR_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}  # ⚠️ хоосон эсвэл буруу format-тай файл байвал зүгээр л хоосон dict буцаана

def save_donators(data):
    with open(DONATOR_FILE, "w") as f:
        json.dump(data, f, indent=4)
    commit_to_github(DONATOR_FILE, "update donator.json")

def get_donator_emoji(data):
    from datetime import datetime, timezone, timedelta

    total = data.get("total_mnt", 0)
    last_donated = data.get("last_donated")

    if not last_donated:
        return None

    donated_time = datetime.fromisoformat(last_donated)
    now = datetime.now(timezone.utc)

    # Хэрвээ 30 хоног хэтэрсэн бол emoji байхгүй
    if (now - donated_time).days > 30:
        return None

    if total >= 30000:
        return "👑"
    elif total >= 10000:
        return "💸"
    else:
        return "💰"

def load_shields():
    if not os.path.exists(SHIELD_FILE):
        return {}
    with open(SHIELD_FILE, "r") as f:
        return json.load(f)

def save_shields(data):
    with open(SHIELD_FILE, "w") as f:
        json.dump(data, f, indent=4)
    commit_to_github(SHIELD_FILE, "update donate_shields.json")

def load_scores():
    if not os.path.exists(SCORE_FILE):
        return {}
    with open(SCORE_FILE, "r") as f:
        return json.load(f)

def save_scores(data):
    try:
        with open(SCORE_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print("✅ scores.json амжилттай хадгалагдлаа.")
        commit_to_github(SCORE_FILE, "update scores.json")
    except Exception as e:
        print("❌ scores.json хадгалах үед алдаа:", e)

def log_score_transaction(uid: str, delta: int, total: int, tier: str, reason: str = ""):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uid": uid,
        "delta": delta,
        "total": total,
        "tier": tier,
        "reason": reason
    }
    print(f"[score_log] {entry}")
    with open(SCORE_LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    commit_to_github(SCORE_LOG_FILE, "append score_log.jsonl")

# Зөвхөн энэ дараалал дагуу tier харуулна (өндөрөөс нам)
TIER_ORDER = ["2-1", "2-2", "2-3", "3-1", "3-2", "3-3", "4-1", "4-2", "4-3"]

# Tier ахих, буурах функц

def promote_tier(current_tier):
    idx = TIER_ORDER.index(current_tier)
    return TIER_ORDER[max(0, idx - 1)]  # ахих


def demote_tier(current_tier):
    idx = TIER_ORDER.index(current_tier)
    return TIER_ORDER[min(len(TIER_ORDER) - 1, idx + 1)]  # буурах


def get_tier(score):
    return "4-1"  # default tier

def commit_to_github(filename, message="update"):
    token = os.environ.get("GITHUB_TOKEN")
    repo = "Tuguldur0107/RZR_bot_v5"
    branch = "main"

    # ⛔️ GitHub дээр path /mnt/data/... биш, зөвхөн filename байх ёстой
    github_path = os.path.basename(filename)

    with open(filename, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    api_url = f"https://api.github.com/repos/{repo}/contents/{github_path}"

    res = requests.get(api_url, headers={"Authorization": f"token {token}"})
    sha = res.json().get("sha")

    data = {
        "message": message,
        "branch": branch,
        "content": content,
        "sha": sha
    }

    r = requests.put(api_url, headers={"Authorization": f"token {token}"}, json=data)
    if r.status_code in [200, 201]:
        print(f"✅ {github_path} GitHub-д хадгалагдлаа.")
    else:
        print(f"❌ GitHub commit алдаа: {r.status_code}", r.text)


def clean_nickname(nick: str) -> str:
    for prefix in TIER_ORDER:
        if nick.startswith(f"{prefix} |"):
            nick = nick[len(prefix) + 2:].strip()
            break
    for emoji in ["💰", "💸", "👑"]:
        if nick.startswith(f"{emoji} "):
            nick = nick[len(emoji) + 1:].strip()
            break
    return nick


def load_shields():
    if not os.path.exists(SHIELD_FILE):
        return {}
    with open(SHIELD_FILE, "r") as f:
        return json.load(f)

def save_shields(data):
    with open(SHIELD_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def github_auto_commit():
    while True:
        await asyncio.sleep(3600)  # 60 минут
        commit_to_github(SCORE_FILE, "auto: scores.json")
        commit_to_github(SCORE_LOG_FILE, "auto: score_log.jsonl")
        commit_to_github(LOG_FILE, "auto: match_log.json")
        commit_to_github(DONATOR_FILE, "auto: donator.json")
        commit_to_github(SHIELD_FILE, "auto: donate_shields.json")

async def update_nicknames_for_users(guild, user_ids: list):
    scores = load_scores()
    donors = load_donators()

    for user_id in user_ids:
        data = scores.get(str(user_id))
        if not data:
            continue

        member = guild.get_member(int(user_id))
        if member:
            tier = data.get("tier", get_tier())
            base_nick = clean_nickname(member.nick or member.name)

            # 💖 Donator emoji оруулна
            emoji = get_donator_emoji(donors.get(str(user_id), {}))
            prefix = f"{emoji + ' ' if emoji else ''}{tier}"

            new_nick = f"{prefix} | {base_nick}"

            try:
                await member.edit(nick=new_nick)
            except discord.Forbidden:
                print(f"⛔️ {member} nickname-г өөрчилж чадсангүй (permission issue).")
            except Exception as e:
                print(f"⚠️ {member} nickname-д алдаа гарлаа: {e}")


# ⏱️ Session хугацаа дууссан эсэх шалгагч task
async def session_timeout_checker():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(60)  # 1 минут тутамд шалгана
        if GAME_SESSION["active"]:
            now = datetime.now(timezone.utc)
            elapsed = now - GAME_SESSION["last_win_time"]
            if elapsed.total_seconds() > 86400:  # 24 цаг = 86400 секунд
                GAME_SESSION["active"] = False
                GAME_SESSION["start_time"] = None
                GAME_SESSION["last_win_time"] = None
                print("🔚 Session автоматаар хаагдлаа (24 цаг өнгөрсөн).")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)


@bot.tree.command(name="ping", description="Ping test")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

@bot.tree.command(name="undo_last_match", description="Сүүлд хийсэн match-ийн оноог буцаана")
async def undo_last_match(interaction: discord.Interaction):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction already responded or expired.")
        return

    try:
        with open(LAST_FILE, "r") as f:
            last = json.load(f)
    except FileNotFoundError:
        await interaction.followup.send("⚠️ Сүүлд бүртгэсэн match олдсонгүй.")
        return

    scores = load_scores()
    changed_ids = []
    guild = interaction.guild

    for uid in last.get("winners", []):
        uid_str = str(uid)
        data = scores.get(uid_str)
        member = guild.get_member(int(uid))

        if data:
            score = data.get("score", 0) - 1
            if score < 0:
                score = 0

            tier = data.get("tier", 4-1)

            scores[uid_str] = {
                "username": data.get("username") or (member.name if member else "unknown"),
                "score": score,
                "tier": tier,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            log_score_transaction(uid_str, -1, score, tier, "undo win")
            changed_ids.append(int(uid))

    for uid in last.get("losers", []):
        uid_str = str(uid)
        data = scores.get(uid_str)
        member = guild.get_member(int(uid))

        if data:
            score = data.get("score", 0) + 1
            if score > 5:
                score = 5

            tier = data.get("tier", 4-1)

            scores[uid_str] = {
                "username": data.get("username") or (member.name if member else "unknown"),
                "score": score,
                "tier": tier,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            log_score_transaction(uid_str, +1, score, tier, "undo loss")
            changed_ids.append(int(uid))

    save_scores(scores)
    await update_nicknames_for_users(interaction.guild, changed_ids)
    commit_to_github(LAST_FILE, "update last_match.json")
    await interaction.followup.send("↩️ Сүүлийн match-ийн оноо буцаагдлаа.")

@bot.tree.command(name="match_history", description="Сүүлийн тоглолтуудын жагсаалтыг харуулна")
async def match_history(interaction: discord.Interaction):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction already responded or expired.")
        return

    try:
        with open(LOG_FILE, "r") as f:
            log = json.load(f)
    except FileNotFoundError:
        await interaction.followup.send("📭 Match log хоосон байна.")
        return

    if not log:
        await interaction.followup.send("📭 Match log хоосон байна.")
        return

    # 🕓 Timestamp-оор эрэмбэлээд сүүлийн 5-г авна
    log = sorted(log, key=lambda x: x.get("timestamp", ""), reverse=True)[:5]

    msg = "📜 **Сүүлийн Match-ууд:**\n"

    for i, entry in enumerate(log, 1):
        ts = entry.get("timestamp", "⏱")
        dt = datetime.fromisoformat(ts).astimezone(timezone(timedelta(hours=8)))
        ts_str = dt.strftime("%Y-%m-%d %H:%M")

        mode = entry.get("mode", "unknown")
        winner = entry.get("winner_team")
        loser = entry.get("loser_team")
        changed = entry.get("changed_players", [])
        teams = entry.get("teams", [])

        msg += f"\n**#{i} | {mode} | {ts_str}**\n"

        for t_num, team in enumerate(teams, start=1):
            tag = "🏆" if t_num == winner else "💔" if t_num == loser else "🎮"
            players = ", ".join(f"<@{uid}>" for uid in team)
            msg += f"{tag} Team {t_num}: {players}\n"

        for ch in changed:
            msg += f"🔁 <@{ch['from']}> → <@{ch['to']}>\n"

    await interaction.followup.send(msg)

@bot.tree.command(name="my_score", description="Таны оноог шалгах")
async def my_score(interaction: discord.Interaction):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction already responded or expired.")
        return

    print("🔥 /my_score эхэллээ")

    scores = load_scores()
    user_id = str(interaction.user.id)
    data = scores.get(user_id)

    if isinstance(data, dict):
        score = data.get("score", 0)
        tier = data.get("tier", 4-1)
        updated = data.get("updated_at")

        msg = f"📿 {interaction.user.mention} таны оноо: {score}\n🎖 Түвшин: **{tier}**"
        if updated:
            try:
                dt = datetime.fromisoformat(updated)
                formatted = dt.strftime("%Y-%m-%d %H:%M")
                msg += f"\n🕓 Сүүлд шинэчлэгдсэн: `{formatted}`"
            except:
                msg += f"\n🕓 Сүүлд шинэчлэгдсэн: `{updated}`"

        await interaction.followup.send(content=msg)
    else:
        await interaction.followup.send(
            content=f"📿 {interaction.user.mention} танд оноо бүртгэгдээгүй байна.\n🎖 Түвшин: **Tier-гүй байна**"
        )

@bot.tree.command(name="scoreboard", description="Бүх тоглогчдын онооны жагсаалт")
async def scoreboard(interaction: discord.Interaction):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction already responded.")
        return

    # ✅ Админ эрх шалгах
    if not interaction.user.guild_permissions.administrator:
        await interaction.followup.send("❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.", ephemeral=True)
        return

    scores = load_scores()

    # 🕓 Сүүлд шинэчлэгдсэн огноо
    latest_update = None
    for data in scores.values():
        if isinstance(data, dict) and "updated_at" in data:
            try:
                t = datetime.fromisoformat(data["updated_at"])
                if not latest_update or t > latest_update:
                    latest_update = t
            except:
                pass

    sorted_scores = sorted(scores.items(),
                           key=lambda x: x[1].get("score", 0)
                           if isinstance(x[1], dict) else 0,
                           reverse=True)

    lines = []
    for user_id, data in sorted_scores:
        if not isinstance(data, dict):
            continue
        member = interaction.guild.get_member(int(user_id))
        if member:
            score = data.get("score", 0)
            tier = data.get("tier", "3-3")

            updated = data.get("updated_at")
            update_str = ""
            if updated:
                try:
                    ts = datetime.fromisoformat(updated).strftime("%Y-%m-%d %H:%M")
                    update_str = f" (🕓 {ts})"
                except:
                    pass

            lines.append(f"Оноо: {score}, Түвшин: {tier} — {member.display_name}{update_str}")

    if not lines:
        await interaction.followup.send("📊 Оноо бүртгэлгүй байна.")
        return

    chunk = "📊 **Scoreboard:**\n"
    if latest_update:
        chunk += f"🕓 Сүүлд шинэчлэгдсэн: `{latest_update.strftime('%Y-%m-%d %H:%M:%S')}`\n\n"

    for line in lines:
        if len(chunk) + len(line) + 1 > 1900:
            await interaction.followup.send(chunk)
            chunk = ""
        chunk += line + "\n"

    if chunk:
        await interaction.followup.send(chunk)

@bot.tree.command(name="user_tier", description="Хэрэглэгчийн түвшинг харуулна")
@app_commands.describe(member="Түвшин шалгах хэрэглэгч")
async def user_tier(interaction: discord.Interaction, member: discord.Member):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction already responded or expired.")
        return

    scores = load_scores()
    user_id = str(member.id)
    data = scores.get(user_id)

    if isinstance(data, dict):
        tier = data.get("tier", 4-1)
        await interaction.followup.send(
            f"🎖 {member.mention} хэрэглэгчийн түвшин: **{tier}**"
        )
    else:
        await interaction.followup.send(
            f"⚠️ {member.mention} хэрэглэгчид оноо/төвшин бүртгэгдээгүй байна."
        )

@bot.tree.command(name="make_team", description="Тоглох багийн тохиргоог эхлүүлнэ")
@app_commands.describe(team_count="Хэдэн багтай байх вэ", players_per_team="Нэг багт хэдэн хүн байх вэ")
async def make_team(interaction: discord.Interaction, team_count: int, players_per_team: int):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction expired.")
        return
       
    # 🔄 Хуучин session-ийг дуусгаж, шинэ тохиргоо эхлүүлнэ
    GAME_SESSION["active"] = False
    GAME_SESSION["start_time"] = None
    GAME_SESSION["last_win_time"] = None

    TEAM_SETUP["initiator_id"] = interaction.user.id
    TEAM_SETUP["team_count"] = team_count
    TEAM_SETUP["players_per_team"] = players_per_team
    TEAM_SETUP["player_ids"] = []
    TEAM_SETUP["teams"] = []
    TEAM_SETUP["changed_players"] = []

    await interaction.followup.send(
        f"🎯 Багийн тохиргоо эхэллээ! Нийт {team_count} баг, нэг багт {players_per_team} хүн байна. "
        f"Тоглогчид /addme гэж бүртгүүлнэ үү.\n"
        f"⏳ **5 минутын дараа автоматаар баг хуваарилна.**")

    async def auto_assign():
        await asyncio.sleep(300)
        fake = type("FakeInteraction", (), {})()
        fake.user = interaction.user
        fake.guild = interaction.guild
        fake.channel = interaction.channel
        fake.response = interaction.response
        fake.followup = interaction.followup
        await make_team_go(fake)

    asyncio.create_task(auto_assign())

@bot.tree.command(name="addme", description="Тоглогчоор бүртгүүлнэ")
async def addme(interaction: discord.Interaction):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction expired.")
        return
    
    if TEAM_SETUP["initiator_id"] is None:
        await interaction.followup.send("⚠️ /make_team командаар эхлүүлсний дараа /addme ашиглана уу.")
        return

    if GAME_SESSION["active"]:
        await interaction.followup.send("⚠️ Session аль хэдийн эхэлсэн байна, дахин бүртгүүлэх боломжгүй.", ephemeral=True)
        return

    user_id = interaction.user.id
    if user_id not in TEAM_SETUP["player_ids"]:
        TEAM_SETUP["player_ids"].append(user_id)
        all_players = ", ".join([f"<@{uid}>" for uid in TEAM_SETUP["player_ids"]])
        await interaction.followup.send(
            f"✅ {interaction.user.mention} амжилттай бүртгэгдлээ!\n"
            f"📋 Бүртгэгдсэн тоглогчид: {all_players}"
        )
    else:
        await interaction.followup.send("⚠️ Та аль хэдийн бүртгэгдсэн байна.", ephemeral=True)
@bot.tree.command(name="make_team_go", description="Бүртгүүлсэн тоглогчдыг багт хуваана")
async def make_team_go(interaction: discord.Interaction):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction expired.")
        return
     
    if interaction.user.id != TEAM_SETUP["initiator_id"]:
        await interaction.followup.send("❌ Зөвхөн тохиргоог эхлүүлсэн хүн баг хуваарилалтыг эхлүүлж болно.")
        return

    team_count = TEAM_SETUP["team_count"]
    players_per_team = TEAM_SETUP["players_per_team"]
    user_ids = TEAM_SETUP["player_ids"]
    total_slots = team_count * players_per_team

    guild = interaction.guild
    scores = load_scores()

    tier_score = {
        "4-3": 0,
        "4-2": 5,
        "4-1": 10,
        "3-3": 15,
        "3-2": 20,
        "3-1": 25,
        "2-3": 30,
        "2-2": 35,
        "2-1": 40
    }

    player_info = []
    for uid in user_ids:
        member = guild.get_member(uid)
        if not member:
            continue
        data = scores.get(str(uid), {"tier": "4-1", "score": 0})
        tier = data.get("tier", 4-1)
        score = data.get("score", 0)
        base = tier_score.get(tier, 5)
        real_score = base + score
        player_info.append({
            "member": member,
            "tier": tier,
            "score": score,
            "real_score": real_score
        })

    teams = [{"players": [], "score": 0} for _ in range(team_count)]
    player_info.sort(key=lambda x: -x["real_score"])

    for player in player_info:
        valid_teams = [t for t in teams if len(t["players"]) < players_per_team]
        if not valid_teams:
            break
        target_team = min(valid_teams, key=lambda t: t["score"])
        target_team["players"].append(player)
        target_team["score"] += player["real_score"]

    assigned_players = [p for t in teams for p in t["players"]]
    unassigned_players = [p for p in player_info if p not in assigned_players]

    emojis = ["🥇", "🥈", "🥉", "🎯", "🔥", "⚡️", "🛡", "🎮", "👾", "🎲"]
    msg = f"**🤖 {len(player_info)} тоглогчийг {team_count} багт хуваалаа (нэг багт {players_per_team} хүн):**\n\n"

    team_ids = []
    for i, team in enumerate(teams, 1):
        emj = emojis[i - 1] if i - 1 < len(emojis) else "🏅"
        msg += f"**{emj} Team {i}** (нийт оноо: `{team['score']}`):\n"
        team_ids.append([p["member"].id for p in team["players"]])
        for p in team["players"]:
            msg += f"• {p['member'].mention} ({p['tier']} / {p['score']:+})\n"
        msg += "\n"

    if unassigned_players:
        msg += "⚠️ **Дараах тоглогчид энэ удаад багт багтаж чадсангүй:**\n"
        for p in unassigned_players:
            msg += f"• {p['member'].mention} ({p['tier']} / {p['score']:+})\n"

    await interaction.followup.send(msg)

    TEAM_SETUP["player_ids"] = [p["member"].id for t in teams for p in t["players"]]
    TEAM_SETUP["teams"] = team_ids

    now = datetime.now(timezone.utc)
    GAME_SESSION["active"] = True
    GAME_SESSION["start_time"] = now
    GAME_SESSION["last_win_time"] = now

    team_log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "make_team_go",
        "teams": TEAM_SETUP["teams"],
        "initiator": interaction.user.id
    }

    try:
        with open("team_log.json", "r") as f:
            team_log = json.load(f)
    except FileNotFoundError:
        team_log = []

    team_log.append(team_log_entry)
    with open("team_log.json", "w") as f:
        json.dump(team_log, f, indent=2)

# 🏆 Winner Team сонгох
@bot.tree.command(name="set_winner_team", description="Хожсон болон хожигдсон багийг зааж оноо өгнө")
@app_commands.describe(winning_team="Хожсон багийн дугаар", losing_team="Хожигдсон багийн дугаар")
async def set_winner_team(interaction: discord.Interaction, winning_team: int, losing_team: int):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction expired.")
        return
        
    if interaction.user.id != TEAM_SETUP.get("initiator_id"):
        await interaction.followup.send("❌ Зөвхөн тохиргоог эхлүүлсэн хүн ажиллуулна.", ephemeral=True)
        return

    if not GAME_SESSION["active"]:
        await interaction.followup.send("⚠️ Session идэвхгүй байна. /make_team_go-оор эхлүүл.", ephemeral=True)
        return

    team_count = TEAM_SETUP["team_count"]
    team_size = TEAM_SETUP["players_per_team"]

    if not (1 <= winning_team <= team_count) or not (1 <= losing_team <= team_count):
        await interaction.followup.send("❌ Багийн дугаар буруу байна.")
        return
    if winning_team == losing_team:
        await interaction.followup.send("⚠️ Хожсон ба хожигдсон баг адил байна.")
        return

    def get_team_user_ids(team_number):
        start = (team_number - 1) * team_size
        end = start + team_size
        return TEAM_SETUP["player_ids"][start:end]

    scores = load_scores()
    shields = load_shields()
    guild = interaction.guild
    changed_ids = []

    winning_ids = get_team_user_ids(winning_team)
    losing_ids = get_team_user_ids(losing_team)

    winners, losers = [], []

    for uid in winning_ids:
        uid_str = str(uid)
        member = guild.get_member(uid)
        data = scores.get(uid_str, {})
        score = data.get("score", 0) + 1
        tier = data.get("tier", 4-1)

        while score >= 5:
            tier = promote_tier(tier)
            score -= 5

        scores[uid_str] = {
            "username": member.name if member else "unknown",
            "score": score,
            "tier": tier,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        log_score_transaction(uid_str, +1, score, tier, "win")

        changed_ids.append(uid)
        if member:
            winners.append(member.mention)

    for uid in losing_ids:
        uid_str = str(uid)
        member = guild.get_member(uid)
        data = scores.get(uid_str, {})
        score = data.get("score", 0)
        tier = data.get("tier", 4-1)

        if await should_deduct(uid_str, shields):
            score -= 1
            while score <= -5:
                tier = demote_tier(tier)
                score += 5

        scores[uid_str] = {
            "username": member.name if member else "unknown",
            "score": score,
            "tier": tier,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        log_score_transaction(uid_str, -1, score, tier, "loss")

        changed_ids.append(uid)
        if member:
            losers.append(member.mention)

    save_scores(scores)
    save_shields(shields)
    await update_nicknames_for_users(guild, changed_ids)

    # 🗃️ Match log хадгалах
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "set_winner_team",
        "teams": TEAM_SETUP.get("teams", []),
        "winner_team": winning_team,
        "loser_team": losing_team,
        "changed_players": TEAM_SETUP.get("changed_players", []),
        "initiator": interaction.user.id
    }

    try:
        with open(LOG_FILE, "r") as f:
            log = json.load(f)
    except FileNotFoundError:
        log = []

    log.append(log_entry)
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)
    commit_to_github(LOG_FILE, "update match_log.json")

    last_entry = {
        "timestamp": log_entry["timestamp"],
        "mode": log_entry["mode"],
        "winners": winning_ids,
        "losers": losing_ids
    }
    with open(LAST_FILE, "w") as f:
        json.dump(last_entry, f, indent=2)
    commit_to_github(LAST_FILE, "update last_match.json")

    await interaction.followup.send(f"🏆 Team {winning_team} оноо авлаа: ✅ +1\n{', '.join(winners)}")
    await interaction.followup.send(f"💔 Team {losing_team} оноо хасагдлаа: ❌ -1\n{', '.join(losers)}")

    GAME_SESSION["last_win_time"] = datetime.now(timezone.utc)

@bot.tree.command(name="change_player", description="Багт тоглогч солих")
@app_commands.describe(from_member="Солигдох тоглогч", to_member="Шинэ тоглогч")
async def change_player(interaction: discord.Interaction, from_member: discord.Member, to_member: discord.Member):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction expired.")
        return
        
    # Зөвхөн эхлүүлэгч ажиллуулах эрхтэй эсэх шалгах
    if interaction.user.id != TEAM_SETUP.get("initiator_id"):
        await interaction.followup.send("❌ Зөвхөн багийн тохиргоог эхлүүлсэн хүн энэ командыг ажиллуулж чадна.", ephemeral=True)
        return

    user_ids = TEAM_SETUP["player_ids"]
    players_per_team = TEAM_SETUP["players_per_team"]
    team_count = TEAM_SETUP["team_count"]

    if from_member.id not in user_ids:
        await interaction.followup.send(f"⚠️ {from_member.mention} багт бүртгэгдээгүй байна.")
        return

    if to_member.id in user_ids:
        await interaction.followup.send(f"⚠️ {to_member.mention} аль хэдийн өөр багт бүртгэгдсэн байна.")
        return

    idx = user_ids.index(from_member.id)
    TEAM_SETUP["player_ids"][idx] = to_member.id

    # 🗃️ Солилцооны log team_log.json руу хадгалах
    team_log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "change_player",
        "teams": TEAM_SETUP.get("teams", []),
        "changed_players": [{"from": from_member.id, "to": to_member.id}],
        "initiator": interaction.user.id
    }

    try:
        with open("team_log.json", "r") as f:
            team_log = json.load(f)
    except FileNotFoundError:
        team_log = []

    team_log.append(team_log_entry)
    with open("team_log.json", "w") as f:
        json.dump(team_log, f, indent=2)

    old_team = (idx // players_per_team) + 1  # Багийн дугаар (1-с эхэлнэ)

    await interaction.followup.send(
        f"🔁 {from_member.mention} → {to_member.mention} солигдлоо!\n"
        f"📌 {from_member.mention} нь Team {old_team}-д байсан."
    )

@bot.tree.command(name="donate_shield", description="Тоглогчид хамгаалалтын удаа онооно")
@app_commands.describe(
    member="Хамгаалалт авах тоглогч",
    count="Хэдэн удаа хамгаалах вэ (default: 1)"
)
async def donate_shield(interaction: discord.Interaction, member: discord.Member, count: int = 1):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction expired.")
        return

    # ✅ Зөвхөн админ хэрэглэгч шалгах
    if not interaction.user.guild_permissions.administrator:
        await interaction.followup.send(
            "❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.",
            ephemeral=True
        )
        return

    if count <= 0:
        await interaction.followup.send("⚠️ Хамгаалалтын тоо 1-с дээш байх ёстой.")
        return

    shields = load_shields()
    uid = str(member.id)
    shields[uid] = shields.get(uid, 0) + count
    save_shields(shields)

    await interaction.followup.send(
        f"🛡️ {member.mention} хэрэглэгчид {count} удаагийн хамгаалалт амжилттай өглөө!"
    )

@bot.tree.command(name="init_scores",
                  description="Бүх гишүүдэд default оноо, tier (4-1) онооно")
async def init_scores(interaction: discord.Interaction):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction expired.")
        return

    # ✅ зөвхөн админ хэрэглэгч ажиллуулна
    if not interaction.user.guild_permissions.administrator:
        await interaction.followup.send(
            "❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.",
            ephemeral=True
        )
        return

    guild = interaction.guild
    scores = load_scores()

    default_tier = "4-1"
    for member in guild.members:
        if member.bot:
            continue
        uid = str(member.id)
        if uid not in scores:
            scores[uid] = {"score": 0, "tier": default_tier}
            try:
                base_nick = member.nick or member.name
                for prefix in TIER_ORDER:
                    if base_nick.startswith(f"{prefix} |"):
                        base_nick = base_nick[len(prefix) + 2:].strip()
                new_nick = f"{default_tier} | {base_nick}"
                await member.edit(nick=new_nick)
            except discord.Forbidden:
                print(f"⛔️ {member} nickname-г өөрчилж чадсангүй.")
            except Exception as e:
                print(f"⚠️ {member} nickname-д алдаа: {e}")

    save_scores(scores)
    await interaction.followup.send(
        "✅ Бүх гишүүдэд оноо болон `4-1` түвшин оноолоо.")

@bot.tree.command(name="set_tier", description="Admin: Хэрэглэгчийн tier-г гараар өөрчилнө")
@app_commands.describe(
    member="Tier өөрчлөх хэрэглэгч",
    new_tier="Шинэ tier (жишээ: 3-2, 4-1)"
)
async def set_tier(interaction: discord.Interaction, member: discord.Member, new_tier: str):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction expired.")
        return
        
    # ✅ зөвхөн админ эрхтэй хэрэглэгч ажиллуулна
    if not interaction.user.guild_permissions.administrator:
        await interaction.followup.send("❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.", ephemeral=True)
        return

    if new_tier not in TIER_ORDER:
        await interaction.followup.send(
            f"❌ Tier: `{new_tier}` олдсонгүй. Зөвхөн дараах байдлаар байна:\n{', '.join(TIER_ORDER)}",
            ephemeral=True
        )
        return

    user_id = str(member.id)
    scores = load_scores()
    if user_id not in scores:
        scores[user_id] = {"score": 0, "tier": new_tier}
    else:
        scores[user_id]["tier"] = new_tier

    save_scores(scores)

    # nickname шинэчлэх
    try:
        base_nick = member.nick or member.name
        for prefix in TIER_ORDER:
            if base_nick.startswith(f"{prefix} |"):
                base_nick = base_nick[len(prefix)+2:].strip()
        new_nick = f"{new_tier} | {base_nick}"
        await member.edit(nick=new_nick)
    except discord.Forbidden:
        await interaction.followup.send(
            "⚠️ Tier амжилттай солигдсон ч nickname өөрчилж чадсангүй (permission issue).",
            ephemeral=True
        )
        return
    except Exception as e:
        await interaction.followup.send(f"⚠️ Алдаа гарлаа: {e}", ephemeral=True)
        return

    await interaction.followup.send(f"✅ {member.mention}-ийн tier-г `{new_tier}` болголоо.")

@bot.tree.command(name="user_score", description="Хэрэглэгчийн оноо болон түвшинг харуулна")
@app_commands.describe(member="Оноог шалгах хэрэглэгч")
async def user_score(interaction: discord.Interaction, member: discord.Member):
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction expired.")
        return

    scores = load_scores()
    user_id = str(member.id)
    data = scores.get(user_id)

    if isinstance(data, dict):
        score = data.get("score", 0)
        tier = data.get("tier", 4-1)
        await interaction.followup.send(
            f"👤 {member.mention} хэрэглэгчийн оноо: {score}\n🎖 Түвшин: **{tier}**"
        )
    else:
        await interaction.followup.send(
            f"👤 {member.mention} хэрэглэгчид оноо бүртгэгдээгүй байна."
        )

@bot.tree.command(name="set_winner_team_fountain", description="Fountain дээр хожсон ба хожигдсон багуудад оноо өгнө")
@app_commands.describe(
    winning_team="Хожсон багийн дугаар (1, 2, 3...)",
    losing_team="Хожигдсон багийн дугаар (1, 2, 3...)"
)
async def set_winner_team_fountain(interaction: discord.Interaction, winning_team: int, losing_team: int):

    # ✅ Эхлээд эрх шалгана
    if interaction.user.id != TEAM_SETUP.get("initiator_id"):
        await interaction.response.send_message("❌ Зөвхөн тохиргоо эхлүүлсэн хүн ажиллуулж чадна.", ephemeral=True)
        return

    if not GAME_SESSION["active"]:
        await interaction.response.send_message("⚠️ Session идэвхгүй байна. /make_team_go-оор эхлүүл.", ephemeral=True)
        return

    if winning_team < 1 or winning_team > TEAM_SETUP["team_count"] or losing_team < 1 or losing_team > TEAM_SETUP["team_count"]:
        await interaction.response.send_message("❌ Багийн дугаар буруу байна.", ephemeral=True)
        return

    # ✅ defer зөвхөн энд
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction-д аль хэдийн хариулсан байна.")
        return

    scores = load_scores()
    guild = interaction.guild
    team_size = TEAM_SETUP["players_per_team"]

    def get_team_user_ids(team_number: int):
        start_idx = (team_number - 1) * team_size
        end_idx = start_idx + team_size
        return TEAM_SETUP["player_ids"][start_idx:end_idx]

    winning_ids = get_team_user_ids(winning_team)
    losing_ids = get_team_user_ids(losing_team)
    changed_ids = []

    for uid in winning_ids:
        uid_str = str(uid)
        member = guild.get_member(uid)
        data = scores.get(uid_str, {})
        score = data.get("score", 0) + 2
        tier = data.get("tier", 4-1)

        while score >= 5:
            tier = promote_tier(tier)
            score -= 5

        scores[uid_str] = {
            "username": member.name if member else "unknown",
            "score": score,
            "tier": tier,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        log_score_transaction(uid_str, +2, score, tier, "fountain win")
        changed_ids.append(uid)

    for uid in losing_ids:
        uid_str = str(uid)
        member = guild.get_member(uid)
        data = scores.get(uid_str, {})
        score = data.get("score", 0) - 2
        tier = data.get("tier", 4-1)

        while score <= -5:
            tier = demote_tier(tier)
            score += 5

        scores[uid_str] = {
            "username": member.name if member else "unknown",
            "score": score,
            "tier": tier,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        log_score_transaction(uid_str, -2, score, tier, "fountain loss")
        changed_ids.append(uid)

    save_scores(scores)
    await update_nicknames_for_users(guild, changed_ids)

    win_mentions = ", ".join([f"<@{uid}>" for uid in winning_ids])
    lose_mentions = ", ".join([f"<@{uid}>" for uid in losing_ids])

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "fountain",
        "teams": TEAM_SETUP.get("teams", []),
        "winner_team": winning_team,
        "loser_team": losing_team,
        "changed_players": TEAM_SETUP.get("changed_players", []),
        "initiator": interaction.user.id
    }

    try:
        with open(LOG_FILE, "r") as f:
            log = json.load(f)
    except FileNotFoundError:
        log = []

    log.append(log_entry)
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)
    commit_to_github(LOG_FILE, "update match_log.json")

    last_entry = {
        "timestamp": log_entry["timestamp"],
        "mode": "fountain",
        "winners": winning_ids,
        "losers": losing_ids
    }
    with open(LAST_FILE, "w") as f:
        json.dump(last_entry, f, indent=2)

    await interaction.followup.send(
        f"🌊 **Fountain оноо өглөө!**\n"
        f"🏆 Хожсон баг (Team {winning_team}): {win_mentions} → **+2**\n"
        f"💔 Хожигдсон баг (Team {losing_team}): {lose_mentions} → **–2**"
    )


@bot.tree.command(name="active_teams", description="Идэвхтэй багуудын жагсаалт")
async def active_teams(interaction: discord.Interaction):
    # ✅ эхлээд session шалгана
    if not GAME_SESSION["active"] or "teams" not in TEAM_SETUP:
        await interaction.response.send_message("⚠️ Session идэвхгүй байна.", ephemeral=True)
        return

    # ✅ defer зөв газарт
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction-д аль хэдийн хариулсан байна.")
        return

    guild = interaction.guild
    msg = "📋 **Идэвхтэй багуудын жагсаалт:**\n"

    for i, team_members in enumerate(TEAM_SETUP["teams"], start=1):
        mentions = []
        for uid in team_members:
            member = guild.get_member(uid)
            mentions.append(member.mention if member else f"<@{uid}>")
        msg += f"\n🥇 **Team {i}:**\n• " + ", ".join(mentions) + "\n"

    await interaction.followup.send(msg)

@bot.tree.command(name="set_team", description="Админ: тоглогчдыг багт бүртгэнэ")
@app_commands.describe(
    team_number="Багийн дугаар",
    mentions="Багийн гишүүдийн mention-ууд (@user @user...)"
)
async def set_team(interaction: discord.Interaction, team_number: int, mentions: str):
    # ✅ Админ эрхийг эхлээд шалгана
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔️ Зөвхөн админ хэрэглэнэ.", ephemeral=True)
        return

    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction-д аль хэдийн хариулсан байна.")
        return

    user_ids = [
        int(word[2:-1].replace("!", "")) for word in mentions.split()
        if word.startswith("<@") and word.endswith(">")
    ]

    if not user_ids:
        await interaction.followup.send("⚠️ Хамгийн багадаа нэг тоглогч mention хийнэ үү.", ephemeral=True)
        return

    if not GAME_SESSION["active"]:
        GAME_SESSION["active"] = True
        now = datetime.now(timezone.utc)
        GAME_SESSION["start_time"] = now
        GAME_SESSION["last_win_time"] = now
        TEAM_SETUP["initiator_id"] = interaction.user.id
        TEAM_SETUP["player_ids"] = []
        TEAM_SETUP["team_count"] = 0
        TEAM_SETUP["players_per_team"] = 0
        TEAM_SETUP["teams"] = []

    already_in = [uid for uid in user_ids if uid in TEAM_SETUP["player_ids"]]
    if already_in:
        duplicates = ", ".join(f"<@{uid}>" for uid in already_in)
        await interaction.followup.send(f"⚠️ Дараах гишүүд аль хэдийн бүртгэгдсэн байна: {duplicates}", ephemeral=True)
        return

    TEAM_SETUP["team_count"] = max(TEAM_SETUP["team_count"], team_number)
    TEAM_SETUP["players_per_team"] = max(TEAM_SETUP["players_per_team"], len(user_ids))
    TEAM_SETUP["player_ids"].extend(user_ids)

    while len(TEAM_SETUP["teams"]) < team_number:
        TEAM_SETUP["teams"].append([])

    TEAM_SETUP["teams"][team_number - 1].extend(user_ids)

    # 🗃️ Log бичнэ
    team_log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "set_team",
        "team_number": team_number,
        "players": user_ids,
        "initiator": interaction.user.id
    }

    try:
        with open("team_log.json", "r") as f:
            team_log = json.load(f)
    except FileNotFoundError:
        team_log = []

    team_log.append(team_log_entry)
    with open("team_log.json", "w") as f:
        json.dump(team_log, f, indent=2)

    mentions_str = ", ".join([f"<@{uid}>" for uid in user_ids])
    await interaction.followup.send(f"✅ **Team {team_number}** бүртгэгдлээ:\n• {mentions_str}")

@bot.tree.command(name="add_team", description="Шинэ багийг тоглож буй session-д нэмнэ")
@app_commands.describe(
    mentions="Шинэ багийн гишүүдийн mention-ууд"
)
async def add_team(interaction: discord.Interaction, mentions: str):
    # ✅ Эхлээд эрх шалгах
    if interaction.user.id != TEAM_SETUP.get("initiator_id"):
        await interaction.response.send_message("❌ Зөвхөн багийн тохиргоог эхлүүлсэн хүн энэ командыг ашиглах эрхтэй.", ephemeral=True)
        return

    if not GAME_SESSION["active"]:
        await interaction.response.send_message("⚠️ Session идэвхгүй байна. /make_team_go-оор эхлүүлнэ үү.", ephemeral=True)
        return

    # ✅ Дараа нь defer
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction-д аль хэдийн хариулсан байна.")
        return

    user_ids = [word[2:-1].replace("!", "") for word in mentions.split() if word.startswith("<@") and word.endswith(">")]
    if len(user_ids) != TEAM_SETUP["players_per_team"]:
        await interaction.followup.send(
            f"⚠️ Шинээр багт бүртгэх гишүүдийн тоо {TEAM_SETUP['players_per_team']}-тэй яг тэнцүү байх ёстой.")
        return

    already_in = [uid for uid in user_ids if int(uid) in TEAM_SETUP["player_ids"]]
    if already_in:
        mention_list = ", ".join([f"<@{uid}>" for uid in already_in])
        await interaction.followup.send(f"⚠️ Дараах тоглогчид аль хэдийн багт бүртгэгдсэн байна: {mention_list}")
        return

    TEAM_SETUP["player_ids"].extend([int(uid) for uid in user_ids])
    TEAM_SETUP["team_count"] += 1

    # ➕ teams-д нэмэх
    TEAM_SETUP["teams"].append([int(uid) for uid in user_ids])

    mentions_text = ", ".join([f"<@{uid}>" for uid in user_ids])
    await interaction.followup.send(
        f"➕ **Шинэ баг нэмэгдлээ (Team {TEAM_SETUP['team_count']})**:\n• {mentions_text}"
    )

@bot.tree.command(name="add_donator", description="Админ: тоглогчийг donator болгоно")
@app_commands.describe(
    member="Donator болгох хэрэглэгч",
    mnt="Хандивласан мөнгө (₮)"
)
async def add_donator(interaction: discord.Interaction, member: discord.Member, mnt: int):
    # ✅ Эхлээд админ шалгана
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.", ephemeral=True)
        return

    # ✅ defer хийнэ
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction-д аль хэдийн хариулсан байна.")
        return

    donors = load_donators()
    uid = str(member.id)
    now = datetime.now(timezone.utc).isoformat()

    if uid not in donors:
        donors[uid] = {
            "total_mnt": mnt,
            "last_donated": now
        }
    else:
        donors[uid]["total_mnt"] += mnt
        donors[uid]["last_donated"] = now

    save_donators(donors)

    scores = load_scores()
    tier = scores.get(uid, {}).get("tier", "4-1")
    base_nick = member.nick or member.name

    for prefix in TIER_ORDER:
        if base_nick.startswith(f"{prefix} |"):
            base_nick = base_nick[len(prefix) + 2:].strip()
    for icon in ["💰", "💸", "👑"]:
        if base_nick.startswith(f"{icon} "):
            base_nick = base_nick[len(icon) + 1:].strip()

    # 🎖 emoji logic
    total_mnt = donors[uid]["total_mnt"]
    if total_mnt >= 30000:
        emoji = "👑"
    elif total_mnt >= 10000:
        emoji = "💸"
    else:
        emoji = "💰"

    new_nick = f"{emoji} {tier} | {base_nick}"

    try:
        await member.edit(nick=new_nick)
    except discord.Forbidden:
        await interaction.followup.send("⚠️ Donator болгосон ч nickname өөрчилж чадсангүй (permission issue).", ephemeral=True)
        return

    await interaction.followup.send(
        f"{emoji} {member.mention} хэрэглэгчийг Donator болголоо! (нийт {total_mnt:,}₮)"
    )

@bot.tree.command(name="donator_list", description="Donator хэрэглэгчдийн жагсаалт")
async def donator_list(interaction: discord.Interaction):
    # ✅ Эхлээд admin шалгана
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Энэ командыг зөвхөн админ хэрэглэгч ашиглаж болно.",
            ephemeral=True
        )
        return

    # ✅ дараа нь interaction-г defer хийнэ
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction-д аль хэдийн хариулсан байна.")
        return

    donors = load_donators()
    if not donors:
        await interaction.followup.send("📭 Donator бүртгэл алга байна.")
        return

    scores = load_scores()
    msg = "💖 **Donators:**\n"
    sorted_donors = sorted(donors.items(), key=lambda x: x[1].get("total_mnt", 0), reverse=True)

    for uid, data in sorted_donors:
        member = interaction.guild.get_member(int(uid))
        if member:
            emoji = get_donator_emoji(data)
            total = data.get("total_mnt", 0)
            tier = scores.get(uid, {}).get("tier", "4-1")

            display_name = member.display_name
            for prefix in TIER_ORDER:
                if display_name.startswith(f"{prefix} |"):
                    display_name = display_name[len(prefix) + 2:].strip()
                    break

            display = f"{emoji} {tier} | {display_name}" if emoji else f"{tier} | {display_name}"
            msg += f"{display} — {total:,}₮\n"


    await interaction.followup.send(msg)

@bot.tree.command(name="all_commands", description="Ботод бүртгэлтэй бүх / командуудыг харуулна")
async def all_commands(interaction: discord.Interaction):
    # ✅ Админ эрх шалгана
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.",
            ephemeral=True
        )
        return

    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction-д аль хэдийн хариулсан байна.")
        return

    commands = await bot.tree.fetch_commands(guild=interaction.guild)

    if not commands:
        await interaction.followup.send("📭 Команд бүртгэгдээгүй байна.")
        return

    msg = "📋 **Ботод бүртгэлтэй командууд:**\n"
    for cmd in commands:
        msg += f"• `/{cmd.name}` — {cmd.description or 'No description'}\n"

    await interaction.followup.send(msg)

@bot.tree.command(name="add_score", description="Хэрэглэгчдийн оноог нэмэгдүүлнэ")
@app_commands.describe(
    mentions="Хэрэглэгчдийг mention хийнэ (@name @name...)",
    points="Нэмэх оноо (эсвэл хасах, default: 1)"
)
async def add_score(interaction: discord.Interaction, mentions: str, points: int = 1):
    # ✅ Эхлээд эрх шалгана
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.",
            ephemeral=True
        )
        return

    # ✅ Дараа нь defer
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction аль хэдийн хариулсан байна.")
        return

    user_ids = [word[2:-1].replace("!", "") for word in mentions.split() if word.startswith("<@") and word.endswith(">")]

    if not user_ids:
        await interaction.followup.send("⚠️ Хэрэглэгчийн mention оруулна уу.")
        return

    scores = load_scores()
    updated = []
    failed = []

    for uid_str in user_ids:
        try:
            member = await interaction.guild.fetch_member(int(uid_str))
        except Exception as e:
            print(f"❌ {uid_str} fetch алдаа: {e}")
            failed.append(uid_str)
            continue

        data = scores.get(uid_str, {})
        old_score = data.get("score", 0)
        old_tier = data.get("tier", 4-1)
        score = old_score + points
        tier = old_tier

        while score >= 5:
            tier = promote_tier(tier)
            score -= 5
        while score <= -5:
            tier = demote_tier(tier)
            score += 5

        scores[uid_str] = {
            "username": member.name,
            "score": score,
            "tier": tier,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        log_score_transaction(uid_str, points, score, tier, "manual")
        updated.append(member)

    save_scores(scores)
    await update_nicknames_for_users(interaction.guild, [int(uid) for uid in user_ids])

    success_mentions = ", ".join([m.mention for m in updated])
    fail_mentions = ", ".join([f"<@{uid}>" for uid in failed])

    msg = f"✅ Оноо `{points}`-оор шинэчлэгдлээ: {success_mentions}" if updated else ""
    if failed:
        msg += f"\n⚠️ Fetch хийхэд алдаа гарсан: {fail_mentions}"

    await interaction.followup.send(msg or "⚠️ Оноо шинэчилсэн хэрэглэгч олдсонгүй.")

@bot.tree.command(name="resync", description="Slash командуудыг дахин сервертэй sync хийнэ (зөвхөн админд)")
async def resync(interaction: discord.Interaction):
    # ✅ Админ шалгана
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔️ Зөвхөн админ л ашиглана.", ephemeral=True)
        return

    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction-д аль хэдийн хариулсан байна.")
        return

    guild = interaction.guild
    if not guild:
        await interaction.followup.send("⚠️ Энэ командыг зөвхөн сервер дээр ажиллуулна уу.", ephemeral=True)
        return

    # 🔄 Командуудыг дахин sync хийнэ
    try:
        bot.tree.clear_commands(guild=guild)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        await interaction.followup.send(f"✅ Командууд `{guild.name}` сервер дээр дахин sync хийгдлээ.")
    except Exception as e:
        await interaction.followup.send(f"⚠️ Sync хийхэд алдаа гарлаа: {e}", ephemeral=True)

@bot.tree.command(name="backup_now", description="Датаг GitHub руу гараар хадгална (зөвхөн админд).")
async def backup_now(interaction: discord.Interaction):
    # ⚠️ Эхлээд эрх шалгана
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔️ Зөвхөн админ л ашиглана.", ephemeral=True)
        return

    # ✅ Дараа нь interaction acknowledge хийнэ
    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction аль хэдийн хариулсан байна.")
        return

    try:
        # 📦 GitHub commit-ууд
        commit_to_github(SCORE_FILE, "manual backup: scores.json")
        commit_to_github(SCORE_LOG_FILE, "manual backup: score_log.jsonl")
        commit_to_github(LOG_FILE, "manual backup: match_log.json")
        commit_to_github(DONATOR_FILE, "manual backup: donator.json")
        commit_to_github(SHIELD_FILE, "manual backup: donate_shields.json")
        await interaction.followup.send("✅ Датаг GitHub руу амжилттай хадгаллаа.")
    except Exception as e:
        await interaction.followup.send(f"❌ Backup хийхэд алдаа гарлаа: {e}", ephemeral=True)

# ✅ Бот асахад ажиллах үйлдлүүд
@bot.event
async def on_ready():
    print(f"🤖 Bot logged in as {bot.user}")
    print("📁 Working directory:", os.getcwd())

    for guild in bot.guilds:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced commands for guild: {guild.name} ({guild.id})")

    # 🕓 Session timeout болон GitHub commit task-уудыг эхлүүлнэ
    asyncio.create_task(session_timeout_checker())
    asyncio.create_task(github_auto_commit())

# ✅ Хэрэглэгч чат бичих бүрт сүүлийн message timestamp хадгалах
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    now = datetime.now(timezone.utc).isoformat()

    try:
        with open("last_message.json", "r") as f:
            last_seen = json.load(f)
    except FileNotFoundError:
        last_seen = {}

    last_seen[user_id] = now

    with open("last_message.json", "w") as f:
        json.dump(last_seen, f, indent=4)

    await bot.process_commands(message)

if __name__ == "__main__":
    print("Starting bot...")
    TOKEN = os.environ["TOKEN"]
    bot.run(TOKEN)
