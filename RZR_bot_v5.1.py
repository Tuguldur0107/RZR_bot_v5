import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio
from datetime import datetime, timezone, timedelta
import base64
import requests
from keep_alive import keep_alive
import re
from openai import OpenAI

# 🔑 Token орчноос авах
OPENAI_API_KEY = os.getenv("GPT_TOKEN")

# ✅ Client үүсгэнэ
client = OpenAI(api_key=OPENAI_API_KEY)

BASE_DIR = "/render_disks/rzr-disk"

start = datetime.now(timezone.utc)
end = start + timedelta(hours=5)

elapsed = end - start  # ⏱ timedelta object

SCORE_FILE       = f"{BASE_DIR}/scores.json"
LOG_FILE         = f"{BASE_DIR}/match_log.json"
LAST_FILE        = f"{BASE_DIR}/last_match.json"
SHIELD_FILE      = f"{BASE_DIR}/donate_shields.json"
DONATOR_FILE     = f"{BASE_DIR}/donator.json"
SCORE_LOG_FILE   = f"{BASE_DIR}/score_log.jsonl"

# 🧠 Тоглоомын Session-н төлөв
GAME_SESSION = {
    "active": False,
    "start_time": None,
    "last_win_time": None
}
TEAM_SETUP = {
    "initiator_id": None,
    "team_count": 0,
    "players_per_team": 0,
    "player_ids": [],
    "teams": [],
    "changed_players": []
}

def init_data_file(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f)

init_data_file(SCORE_FILE, {})
init_data_file(LOG_FILE, [])
init_data_file(LAST_FILE, {})
init_data_file(SHIELD_FILE, {})
init_data_file(DONATOR_FILE, {})
init_data_file(SCORE_LOG_FILE, [])

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
    except Exception as e:
        print("❌ scores.json хадгалах үед алдаа:", e)

def log_score_transaction(uid, delta, total, tier, reason):
    print(f"[score_log] Logging: {uid}, Δ{delta}, T{total}, {tier}, {reason}")  # ← log шалгах
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uid": str(uid),
        "delta": delta,
        "total": total,
        "tier": tier,
        "reason": reason
    }
    try:
        with open(SCORE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"❌ score_log.jsonl write error: {e}")

# Зөвхөн энэ дараалал дагуу tier харуулна (өндөрөөс нам)
TIER_ORDER = ["2-1", "2-2", "2-3", "3-1", "3-2", "3-3", "4-1", "4-2", "4-3"]

# Tier ахих, буурах функц

def promote_tier(current_tier):
    idx = TIER_ORDER.index(current_tier)
    return TIER_ORDER[max(0, idx - 1)]  # ахих

def demote_tier(current_tier):
    idx = TIER_ORDER.index(current_tier)
    return TIER_ORDER[min(len(TIER_ORDER) - 1, idx + 1)]  # буурах

def get_tier():
    return "4-1"  # default tier

def commit_to_github_multi(file_list, message="update"):
    token = os.environ.get("GITHUB_TOKEN")
    repo = "Tuguldur0107/RZR_bot_v5"
    branch = "main"

    headers = {"Authorization": f"token {token}"}

    for filepath in file_list:
        github_path = os.path.basename(filepath)

        with open(filepath, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")

        api_url = f"https://api.github.com/repos/{repo}/contents/{github_path}"

        # 👉 sha авах
        res = requests.get(api_url, headers=headers)
        sha = res.json().get("sha")

        data = {
            "message": message,
            "branch": branch,
            "content": content,
            "sha": sha
        }

        r = requests.put(api_url, headers=headers, json=data)
        if r.status_code in [200, 201]:
            print(f"✅ {github_path} GitHub-д хадгалагдлаа.")
        else:
            print(f"❌ {github_path} commit алдаа: {r.status_code}", r.text)
    
def get_team_user_ids(team_number):  # 👈 энд зөө
    teams = TEAM_SETUP.get("teams", [])
    if 1 <= team_number <= len(teams):
        return teams[team_number - 1]
    return []

def clean_nickname(nick):
    if not nick:
        return ""

    if "|" in nick:
        nick = nick.split("|", 1)[1].strip()

    return nick

def tier_emoji(tier):
    return {
        "4-3": "⚫️",
        "4-2": "⚫️",
        "4-1": "⚫️",
        "3-3": "⚫️",
        "3-2": "⚫️",
        "3-1": "⚫️",
        "2-3": "⚫️",
        "2-2": "⚫️",
        "2-1": "⚫️"
    }.get(tier, "❓")

def load_shields():
    if not os.path.exists(SHIELD_FILE):
        return {}
    with open(SHIELD_FILE, "r") as f:
        return json.load(f)

def save_shields(data):
    with open(SHIELD_FILE, "w") as f:
        json.dump(data, f, indent=4)

# 🧠 Tier + Score-г тооцоолох
TIER_POINTS = {
    "4-3": 0,
    "4-2": 5,
    "4-1": 10,
    "3-3": 15,
    "3-2": 20,
    "3-1": 25,
    "2-3": 30,
    "2-2": 35,
    "2-1": 40,
    "1-3": 45,
    "1-2": 50,
    "1-1": 55,
}

def tier_score(data):
    tier = data.get("tier", "4-3")
    score = data.get("score", 0)
    return TIER_POINTS.get(tier, 0) + score

# 🐍 Snake хуваарилалт
def assign_snake(scores, team_count, players_per_team):
    buckets = [[] for _ in range(players_per_team)]
    for i, s in enumerate(scores):
        buckets[i % players_per_team].append(s)
    teams = [[] for _ in range(team_count)]
    for idx, bucket in enumerate(buckets):
        direction = 1 if idx % 2 == 0 else -1
        for i, s in enumerate(bucket):
            t = i if direction == 1 else (team_count - 1 - i)
            teams[t % team_count].append(s)
    return teams

# ⚖️ Greedy хувилбар
def assign_greedy(scores, team_count, players_per_team):
    teams = [[] for _ in range(team_count)]
    team_totals = [0] * team_count
    for s in scores:
        idx = min(range(team_count), key=lambda i: (len(teams[i]) >= players_per_team, team_totals[i]))
        teams[idx].append(s)
        team_totals[idx] += s
    return teams

# ➖ Зөрүү тооцох
def calc_diff(teams):
    totals = [sum(t) for t in teams]
    return max(totals) - min(totals)

def call_gpt_balance_api(team_count, players_per_team, player_ids, scores):
    if not OPENAI_API_KEY:
        raise ValueError("❌ OPENAI_API_KEY тодорхойлогдоогүй байна.")

    # Tier + score нийлбэрийг тооцоолж оноо гаргана
    player_scores = []
    for uid in player_ids:
        data = scores.get(str(uid), {})
        power = tier_score(data)
        player_scores.append({"id": uid, "power": power})

    prompt = f"""
{team_count} багт {players_per_team} хүнтэйгээр дараах тоглогчдыг онооны дагуу хамгийн тэнцүү хуваа.
Тоглогчид: {player_scores}
Хэрвээ баг дотор онооны зөрүү их байвал, хамгийн их оноотой тоглогчийг солих замаар онооны зөрүүг багасга.
JSON зөвхөн дараах бүтэцтэй буцаа:
{{"teams": [[123,456,789], [234,567,890], [321,654,987]]}}
""".strip()

    print("📡 GPT-д хүсэлт илгээж байна...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You're a helpful assistant that balances teams."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=1024,
            seed=42,
            stream=False,
            n=1,
            logprobs=False,
            user="rzr_balance_bot",
            logit_bias={},
            response_format={ "type": "json_object" },
            store=True
        )
    except Exception as e:
        print("❌ GPT API chat.completions.create алдаа:", e)
        raise

    try:
        content = response.choices[0].message.content
        print("📥 GPT response content:\n", content)
    except Exception as e:
        print("❌ GPT response structure алдаа:", e)
        raise

    try:
        parsed = json.loads(content)
        teams = parsed.get("teams", [])
        if not isinstance(teams, list) or not all(isinstance(team, list) for team in teams):
            raise ValueError("⚠️ GPT JSON бүтэц буруу байна: 'teams' нь list[list[int]] биш.")
        return teams
    except json.JSONDecodeError as e:
        print("❌ GPT JSON parse алдаа:", e)
        raise
    except Exception as e:
        print("❌ GPT JSON бүтэц алдаа:", e)
        raise

def test_call_gpt_balance_api():
    team_count = 2
    players_per_team = 3
    player_scores = [
        {"id": 1001, "score": 55},
        {"id": 1002, "score": 48},
        {"id": 1003, "score": 30},
        {"id": 1004, "score": 35},
        {"id": 1005, "score": 10},
        {"id": 1006, "score": 5}
    ]

    # GPT-д дамжуулахад хэрэгтэй `scores` dict үүсгэнэ
    dummy_scores = {
        str(p["id"]): {"score": p["score"], "tier": "4-1"}  # tier_score() ашиглаж болно
        for p in player_scores
    }

    try:
        teams = call_gpt_balance_api(
            team_count,
            players_per_team,
            [p["id"] for p in player_scores],
            dummy_scores
        )
        print("✅ Teams received from GPT:", teams)
    except Exception as e:
        print("❌ Тест дээр алдаа гарлаа:", e)

async def github_auto_commit():
    while True:
        await asyncio.sleep(3600)  # 60 минут
        file_list = [SCORE_FILE, SCORE_LOG_FILE, LOG_FILE, DONATOR_FILE, SHIELD_FILE]
        commit_to_github_multi(file_list, "auto: all log files")

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
            base_nick = clean_nickname(member.display_name)  # ✅ display_name + clean

            donor_data = donors.get(str(user_id), {})
            emoji = get_donator_emoji(donor_data) or tier_emoji(tier)

            prefix = f"{emoji} {tier}" if emoji else tier
            new_nick = f"{prefix} | {base_nick}"

            if member.nick == new_nick:
                continue  # 🤝 Яг ижил бол алгас

            try:
                await member.edit(nick=new_nick)
            except discord.Forbidden:
                print(f"⛔️ {member} nickname-г өөрчилж чадсангүй.")
            except Exception as e:
                print(f"⚠️ {member} nickname-д алдаа гарлаа: {e}")

# ⏱️ Session хугацаа дууссан эсэх шалгагч task
async def session_timeout_checker():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(60)  # 1 минут тутамд шалгана
        if GAME_SESSION["active"]:
            now = datetime.now(timezone.utc)
            elapsed = now - GAME_SESSION["last_make_team_time"]
            if elapsed.total_seconds() > 86400:  # 24 цаг = 86400 секунд
                GAME_SESSION["active"] = False
                GAME_SESSION["start_time"] = None
                GAME_SESSION["last_win_time"] = None
                GAME_SESSION["last_make_team_time"] = None
                print("🔚 Session автоматаар хаагдлаа (24 цаг өнгөрсөн).")

async def should_deduct(uid: str, shields: dict) -> bool:
    if shields.get(uid, 0) > 0:
        shields[uid] -= 1
        return False  # 🛡 хамгаалалт байсан, оноо хасахгүй
    return True  # хамгаалалт байхгүй → оноо хасна

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.tree.command(name="ping", description="Ping test")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

@bot.tree.command(name="make_team", description="Тоглох багийн тохиргоог эхлүүлнэ")
@app_commands.describe(team_count="Хэдэн багтай байх вэ", players_per_team="Нэг багт хэдэн хүн байх вэ")
async def make_team(interaction: discord.Interaction, team_count: int, players_per_team: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔️ Зөвхөн админ хэрэглэнэ.", ephemeral=True)
        return

    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction expired.")
        return

    # 🛑 Session байсан бол шууд хаана
    if GAME_SESSION["active"]:
        GAME_SESSION["active"] = False
        GAME_SESSION["start_time"] = None
        GAME_SESSION["last_win_time"] = None
        GAME_SESSION["last_make_team_time"] = None
        GAME_SESSION["can_add"] = False

    # 🧠 Шинэ session эхлүүлнэ
    now = datetime.now(timezone.utc)
    GAME_SESSION["active"] = True
    GAME_SESSION["start_time"] = now
    GAME_SESSION["last_win_time"] = now
    GAME_SESSION["last_make_team_time"] = now
    GAME_SESSION["can_add"] = True

    TEAM_SETUP["team_count"] = team_count
    TEAM_SETUP["players_per_team"] = players_per_team
    TEAM_SETUP["player_ids"] = []
    TEAM_SETUP["teams"] = []
    TEAM_SETUP["changed_players"] = []

    await interaction.followup.send(
        f"🔄 Өмнөх session хаагдаж, шинэ багийн тохиргоо эхэллээ!\n"
        f"📦 Нийт {team_count} баг, нэг багт {players_per_team} хүн байна.\n"
        f"🎮 Тоглогчид `/addme` гэж бүртгүүлнэ үү."
    )

@bot.tree.command(name="addme", description="Тоглоомд оролцохоор бүртгүүлнэ")
async def addme(interaction: discord.Interaction):
    if not GAME_SESSION["active"]:
        await interaction.response.send_message("⚠️ Session идэвхгүй байна.", ephemeral=True)
        return
    if not GAME_SESSION.get("can_add", True):
        await interaction.response.send_message("🛑 Одоо бүртгүүлж болохгүй. Баг аль хэдийн хуваарилагдсан байна.", ephemeral=True)
        return

    now = datetime.now(timezone.utc)
    start_time = GAME_SESSION.get("start_time")
    last_win_time = GAME_SESSION.get("last_win_time")

    # ❌ make_team хийгдсэнээс хойш 5 минут өнгөрсөн бол бүртгэхгүй
    if start_time and (now - start_time).total_seconds() > 300:
        await interaction.response.send_message("⏰ Бүртгэлийн хугацаа дууссан тул оролцох боломжгүй.", ephemeral=True)
        return

    # ❌ Хэрвээ тэмцээн эхэлсэн бол бүртгэхгүй
    if TEAM_SETUP.get("teams") and any(len(team) > 0 for team in TEAM_SETUP["teams"]):
        await interaction.response.send_message("🚫 Тэмцээн аль хэдийн эхэлсэн тул бүртгэх боломжгүй.", ephemeral=True)
        return

    user_id = interaction.user.id
    if user_id in TEAM_SETUP["player_ids"]:
        await interaction.response.send_message("⚠️ Та аль хэдийн бүртгэгдсэн байна.", ephemeral=True)
        return

    TEAM_SETUP["player_ids"].append(user_id)
    total = len(TEAM_SETUP.get("player_ids", []))

    await interaction.response.send_message(
        f"✅ {interaction.user.mention} тоглоомд бүртгэгдлээ! (Нийт: **{total}** тоглогч)"
    )

@bot.tree.command(name="make_team_go", description="Хамгийн тэнцвэртэй хувилбараар баг хуваарилна")
async def make_team_go(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔️ Зөвхөн админ хэрэглэнэ.", ephemeral=True)
        return

    if not GAME_SESSION["active"]:
        await interaction.response.send_message("⚠️ Session идэвхгүй байна. /make_team коммандоор эхлүүлнэ үү.", ephemeral=True)
        return

    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        return

    guild = interaction.guild
    player_ids = TEAM_SETUP["player_ids"]
    team_count = TEAM_SETUP["team_count"]
    players_per_team = TEAM_SETUP["players_per_team"]
    total_slots = team_count * players_per_team

    if len(player_ids) < total_slots:
        await interaction.followup.send(
            f"⚠️ {team_count} баг бүрдэхийн тулд нийт {total_slots} тоглогч бүртгэгдэх ёстой, одоогоор {len(player_ids)} байна."
        )
        return

    scores = load_scores()
    player_scores = []
    uid_map = {}

    for uid in player_ids:
        data = scores.get(str(uid), {})
        ts = tier_score(data)
        player_scores.append(ts)
        uid_map[ts] = uid_map.get(ts, []) + [uid]

    sorted_scores = sorted(player_scores, reverse=True)
    snake_teams = assign_snake(sorted_scores, team_count, players_per_team)
    greedy_teams = assign_greedy(sorted_scores, team_count, players_per_team)
    best_team_scores = greedy_teams if calc_diff(greedy_teams) <= calc_diff(snake_teams) else snake_teams

    final_teams = [[] for _ in range(team_count)]
    used_uids = set()

    for i, team in enumerate(best_team_scores):
        for score in team:
            for uid in uid_map[score]:
                if uid not in used_uids:
                    final_teams[i].append(uid)
                    used_uids.add(uid)
                    break

    TEAM_SETUP["teams"] = final_teams
    GAME_SESSION["last_win_time"] = datetime.now(timezone.utc)  # 🕓 Session шинэчилнэ
    GAME_SESSION["can_add"] = False

    team_emojis = ["🏆", "🥈", "🥉", "🎯", "🔥", "🚀", "🎮", "🛡️", "⚔️", "🧠"]
    msg_lines = [f"🤖 **{len(player_ids)} тоглогчийг {team_count} багт хувиарлалаа (нэг багт {players_per_team} хүн):**"]

    for i, team in enumerate(final_teams):
        emoji = team_emojis[i % len(team_emojis)]
        team_total = 0
        team_lines = []

        for uid in team:
            data = scores.get(str(uid), {})
            total = tier_score(data)
            team_total += total
            team_lines.append(f"- <@{uid}> (тоглогчын оноо: {total})")

        msg_lines.append(f"\n{emoji} **Team {i + 1}** (нийт оноо: `{team_total}` 🧮):\n" + "\n".join(team_lines))

    left_out = [uid for uid in player_ids if uid not in used_uids]
    if left_out:
        mentions = "\n• ".join(f"<@{uid}>" for uid in left_out)
        msg_lines.append(f"\n⚠️ **Дараах тоглогчид энэ удаад багт багтаж чадсангүй:**\n• {mentions}")

    await interaction.followup.send("\n".join(msg_lines))

@bot.tree.command(name="gpt_go", description="GPT-ээр онооны баланс хийж баг хуваарилна")
async def gpt_go(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔️ Зөвхөн админ хэрэглэнэ.", ephemeral=True)
        return

    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        return

    guild = interaction.guild
    team_count = TEAM_SETUP["team_count"]
    players_per_team = TEAM_SETUP["players_per_team"]
    total_slots = team_count * players_per_team
    player_ids = TEAM_SETUP["player_ids"]

    scores = load_scores()
    player_scores = []

    for uid in player_ids:
        data = scores.get(str(uid), {})
        ts = tier_score(data)
        player_scores.append({"id": uid, "score": ts})

    if len(player_scores) > total_slots:
        player_scores = sorted(player_scores, key=lambda x: x["score"], reverse=True)[:total_slots]
        player_ids = [p["id"] for p in player_scores]

    try:
        teams = call_gpt_balance_api(team_count, players_per_team, player_ids, scores)
    except Exception as e:
        print("❌ GPT API error:", e)
        await interaction.followup.send(
            "⚠️ GPT-ээр баг хуваарилах үед алдаа гарлаа. Түр зуурын асуудал байж болзошгүй.\n"
            "⏳ Дараа дахин оролдоно уу эсвэл `/make_team_go` командыг ашиглаарай."
        )
        return

    TEAM_SETUP["teams"] = teams
    GAME_SESSION["last_win_time"] = datetime.now(timezone.utc)

    used_uids = set(uid for team in teams for uid in team)
    team_emojis = ["🥇", "🥈", "🥉", "🎯", "🔥", "🚀", "🎮", "🛡️", "⚔️", "🧠"]

    lines = ["🤖 **ChatGPT-ээр тэнцвэржүүлсэн багууд:**"]
    for i, team in enumerate(teams):
        emoji = team_emojis[i % len(team_emojis)]
        total = sum(tier_score(scores.get(str(uid), {})) for uid in team)
        lines.append(f"\n{emoji} **Team {i + 1}** (нийт оноо: `{total}` 🧮):")
        for uid in team:
            data = scores.get(str(uid), {})
            total_score = tier_score(data)
            lines.append(f"- <@{uid}> (тоглогчын оноо: {total_score})")

    left_out = [uid for uid in TEAM_SETUP["player_ids"] if uid not in used_uids]
    if left_out:
        mentions = "\n• ".join(f"<@{uid}>" for uid in left_out)
        lines.append(f"\n⚠️ **Дараах тоглогчид энэ удаад багт багтаж чадсангүй:**\n• {mentions}")

    await interaction.followup.send("\n".join(lines))

@bot.tree.command(name="set_winner_team", description="Хожсон болон хожигдсон багийг зааж оноо өгнө")
@app_commands.describe(winning_team="Хожсон багийн дугаар", losing_team="Хожигдсон багийн дугаар")
async def set_winner_team(interaction: discord.Interaction, winning_team: int, losing_team: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔️ Зөвхөн админ хэрэглэнэ.", ephemeral=True)
        return

    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction expired.")
        return

    if not GAME_SESSION["active"]:
        await interaction.followup.send("⚠️ Session идэвхгүй байна. /make_team_go-оор эхлүүл.", ephemeral=True)
        return

    team_count = TEAM_SETUP["team_count"]
    if not (1 <= winning_team <= team_count) or not (1 <= losing_team <= team_count):
        await interaction.followup.send("❌ Багийн дугаар буруу байна.")
        return
    if winning_team == losing_team:
        await interaction.followup.send("⚠️ Хожсон ба хожигдсон баг адил байна.")
        return

    scores = load_scores()
    shields = load_shields()
    guild = interaction.guild
    changed_ids = []

    winning_ids = get_team_user_ids(winning_team)
    losing_ids = get_team_user_ids(losing_team)
    winners, losers = []

    for uid in winning_ids:
        uid_str = str(uid)
        member = guild.get_member(uid)
        data = scores.get(uid_str, {})
        score = data.get("score", 0) + 1
        tier = data.get("tier", get_tier())

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
        score = data.get("score", 0) - 1
        tier = data.get("tier", get_tier())

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

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "set_winner_team",
        "teams": TEAM_SETUP.get("teams", []),
        "winner_team": winning_team,
        "loser_team": losing_team,
        "changed_players": changed_ids,
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

    with open(LAST_FILE, "w") as f:
        json.dump({
            "timestamp": log_entry["timestamp"],
            "mode": log_entry["mode"],
            "winners": winning_ids,
            "losers": losing_ids
        }, f, indent=2)

    await interaction.followup.send(
        f"🏆 **Team {winning_team} оноо авлаа:** ✅ +1\n{', '.join(winners)}\n\n"
        f"💔 **Team {losing_team} оноо хасагдлаа:** ❌ -1\n{', '.join(losers)}"
    )

    GAME_SESSION["last_win_time"] = datetime.now(timezone.utc)

@bot.tree.command(name="set_winner_team_fountain", description="Fountain дээр хожсон ба хожигдсон багуудад оноо өгнө")
@app_commands.describe(
    winning_team="Хожсон багийн дугаар (1, 2, 3...)",
    losing_team="Хожигдсон багийн дугаар (1, 2, 3...)"
)
async def set_winner_team_fountain(interaction: discord.Interaction, winning_team: int, losing_team: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔️ Зөвхөн админ хэрэглэнэ.", ephemeral=True)
        return

    if not GAME_SESSION["active"]:
        await interaction.response.send_message("⚠️ Session идэвхгүй байна. /make_team_go-оор эхлүүл.", ephemeral=True)
        return

    if winning_team < 1 or winning_team > TEAM_SETUP["team_count"] or losing_team < 1 or losing_team > TEAM_SETUP["team_count"]:
        await interaction.response.send_message("❌ Багийн дугаар буруу байна.", ephemeral=True)
        return

    if winning_team == losing_team:
        await interaction.response.send_message("⚠️ Хожсон ба хожигдсон баг адил байна.", ephemeral=True)
        return

    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction-д аль хэдийн хариулсан байна.")
        return

    scores = load_scores()
    guild = interaction.guild
    changed_ids = []

    winning_ids = get_team_user_ids(winning_team)
    losing_ids = get_team_user_ids(losing_team)

    for uid in winning_ids:
        uid_str = str(uid)
        member = guild.get_member(uid)
        data = scores.get(uid_str, {})
        score = data.get("score", 0) + 2
        tier = data.get("tier", get_tier())

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
        tier = data.get("tier", get_tier())

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
        "changed_players": changed_ids,
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

    with open(LAST_FILE, "w") as f:
        json.dump({
            "timestamp": log_entry["timestamp"],
            "mode": log_entry["mode"],
            "winners": winning_ids,
            "losers": losing_ids
        }, f, indent=2)

    GAME_SESSION["last_win_time"] = datetime.now(timezone.utc)

    await interaction.followup.send(
        f"🌊 **Fountain оноо өглөө!**\n"
        f"🏆 Хожсон баг (Team {winning_team}): {win_mentions} → **+2**\n"
        f"💔 Хожигдсон баг (Team {losing_team}): {lose_mentions} → **–2**"
    )

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

            tier = data.get("tier", get_tier())

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

            tier = data.get("tier", get_tier())

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

@bot.tree.command(name="add_donator", description="Админ: тоглогчийг donator болгоно")
@app_commands.describe(
    member="Donator болгох хэрэглэгч",
    mnt="Хандивласан мөнгө (₮)"
)
async def add_donator(interaction: discord.Interaction, member: discord.Member, mnt: int):
    # ✅ Админ шалгах
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.", ephemeral=True)
        return

    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction-д аль хэдийн хариулсан байна.")
        return

    # ✅ Donator мэдээллийг хадгалах
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

    # ✅ Nickname-г update_nicknames_for_users ашиглан цэвэрхэн өөрчилнө
    await update_nicknames_for_users(interaction.guild, [member.id])

    total_mnt = donors[uid]["total_mnt"]
    await interaction.followup.send(
        f"🎉 {member.mention} хэрэглэгчийг Donator болголоо! (нийт {total_mnt:,}₮)"
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

    # ✅ Defer
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

        # ✅ Оноо болон tier тооцоолол
        data = scores.get(uid_str, {})
        old_score = data.get("score", 0)
        old_tier = data.get("tier", get_tier())
        score = old_score + points
        tier = old_tier

        while score >= 5:
            tier = promote_tier(tier)
            score -= 5
        while score <= -5:
            tier = demote_tier(tier)
            score += 5

        # ✅ Оноо хадгална
        scores[uid_str] = {
            "username": member.name,
            "score": score,
            "tier": tier,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        log_score_transaction(uid_str, points, score, tier, "manual")
        save_scores(scores)  # <<== энэ мөрийг заавал нэм
        updated.append(member)

        # ✅ Нэрийг төвлөрсөн функцээр шинэчилнэ
        await update_nicknames_for_users(interaction.guild, [m.id for m in updated])

    # ✅ Хариу илгээнэ
    if updated:
        await interaction.followup.send(f"✅ Оноо {points:+}–оор шинэчлэгдлээ: {', '.join([member.mention for member in updated])}")
    elif failed:
        await interaction.followup.send("⚠️ Зарим хэрэглэгчийн мэдээлэл олдсонгүй.")

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

    # ✅ nickname-г төвлөрсөн функцээр шинэчилнэ
    await update_nicknames_for_users(interaction.guild, [user_id])

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
        tier = data.get("tier", get_tier())
        await interaction.followup.send(
            f"👤 {member.mention} хэрэглэгчийн оноо: {score}\n🎖 Түвшин: **{tier}**"
        )
    else:
        await interaction.followup.send(
            f"👤 {member.mention} хэрэглэгчид оноо бүртгэгдээгүй байна."
        )

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
        tier = data.get("tier", get_tier())
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

@bot.tree.command(name="backup_now", description="Датаг GitHub руу гараар хадгална (зөвхөн админд).")
async def backup_now(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔️ Зөвхөн админ л ашиглана.", ephemeral=True)
        return

    try:
        await interaction.response.defer(thinking=True)
    except discord.errors.InteractionResponded:
        print("❌ Interaction аль хэдийн хариулсан байна.")
        return

    try:
        file_list = [SCORE_FILE, SCORE_LOG_FILE, LOG_FILE, DONATOR_FILE, SHIELD_FILE]
        commit_to_github_multi(file_list, "manual backup: all log files")
        await interaction.followup.send("✅ Бүх log файлуудыг GitHub руу хадгаллаа.")
    except Exception as e:
        await interaction.followup.send(f"❌ Backup хийхэд алдаа гарлаа: {e}", ephemeral=True)

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

@bot.tree.command(name="whois", description="Mention хийсэн хэрэглэгчийн нэрийг харуулна")
@app_commands.describe(mention="Хэрэглэгчийн mention (@name) хэлбэрээр")
async def whois(interaction: discord.Interaction, mention: str):
    try:
        uid = int(mention.strip("<@!>"))
        member = await interaction.guild.fetch_member(uid)
        await interaction.response.send_message(f"🕵️‍♂️ Энэ ID: `{uid}` → {member.mention} / Нэр: `{member.display_name}`")
    except Exception as e:
        await interaction.response.send_message(f"❌ Олдсонгүй: {e}")

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

@bot.event
async def on_ready():
    print(f"🤖 Bot logged in as {bot.user}")
    print("📁 Working directory:", os.getcwd())
    bot.loop.create_task(session_timeout_checker())
    bot.loop.create_task(github_auto_commit())

    for guild in bot.guilds:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced commands for guild: {guild.name} ({guild.id})")

    # 🕓 Session timeout болон GitHub commit task-уудыг эхлүүлнэ
    asyncio.create_task(session_timeout_checker())
    asyncio.create_task(github_auto_commit())

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

async def main():
    #from copy_from_github_to_volume import copy_files_from_app_to_volume
    #copy_files_from_app_to_volume()

    keep_alive()
    await bot.start(os.environ["TOKEN"])       # ⚠️ bot.run биш

if __name__ == "__main__":
    print("🚀 Starting bot...")
    test_call_gpt_balance_api()
    asyncio.run(main())