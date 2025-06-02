import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import random
import asyncio
from datetime import datetime, timezone, timedelta

SCORE_FILE = "scores.json"
LOG_FILE = "match_log.json"
LAST_FILE = "last_match.json"
SHIELD_FILE = "donate_shields.json"
DONATOR_FILE = "donator.json"

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

def is_vip(uid):
    donors = load_donators()
    return str(uid) in donors

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
    with open(SCORE_FILE, "w") as f:
        json.dump(data, f, indent=4)


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


intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)


async def update_all_nicknames(guild):
    scores = load_scores()
    for user_id, data in scores.items():
        member = guild.get_member(int(user_id))
        if member:
            score = data.get("score", 0)
            tier = data.get("tier", "4-1")
            try:
                base_nick = member.nick or member.name
                for prefix in TIER_ORDER:
                    if base_nick.startswith(f"{prefix} |"):
                        base_nick = base_nick[len(prefix) + 2:].strip()
                new_nick = f"{tier} | {base_nick}"
                await member.edit(nick=new_nick)
            except discord.Forbidden:
                print(
                    f"⛔️ {member} nickname-г өөрчилж чадсангүй (permission issue)."
                )
            except Exception as e:
                print(f"⚠️ {member} nickname болоход алдаа гарлаа: {e}")
    save_scores(scores)


@bot.tree.command(name="ping", description="Ping test")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

async def update_nicknames_for_users(guild, user_ids: list):
    scores = load_scores()
    for user_id in user_ids:
        data = scores.get(str(user_id))
        if not data:
            continue
        member = guild.get_member(int(user_id))
        if member:
            tier = data.get("tier", "4-1")
            try:
                base_nick = member.nick or member.name
                for prefix in TIER_ORDER:
                    if base_nick.startswith(f"{prefix} |"):
                        base_nick = base_nick[len(prefix)+2:].strip()
                new_nick = f"{tier} | {base_nick}"
                await member.edit(nick=new_nick)
            except discord.Forbidden:
                print(f"⛔️ {member} nickname-г өөрчилж чадсангүй (permission issue).")
            except Exception as e:
                print(f"⚠️ {member} nickname-д алдаа гарлаа: {e}")

@bot.tree.command(name="match3", description="3v3 match result")
@app_commands.describe(winner1="Ялагч 1",
                       winner2="Ялагч 2",
                       winner3="Ялагч 3",
                       loser1="Ялагдагч 1",
                       loser2="Ялагдагч 2",
                       loser3="Ялагдагч 3")
async def match3(interaction: discord.Interaction, winner1: discord.Member,
                 winner2: discord.Member, winner3: discord.Member,
                 loser1: discord.Member, loser2: discord.Member,
                 loser3: discord.Member):

    await interaction.response.defer(thinking=True)

    all_winners = [winner1, winner2, winner3]
    all_losers = [loser1, loser2, loser3]

    if len(set(all_winners + all_losers)) < 6:
        await interaction.followup.send("❌ Тоглогчид давхцаж байна!")
        return

    scores = load_scores()

    for player in all_winners:
        uid = str(player.id)
        if not isinstance(scores.get(uid), dict):
            scores[uid] = {"score": 0, "tier": "4-1"}
        scores[uid]["score"] += 1
        if scores[uid]["score"] >= 5:
            scores[uid]["tier"] = promote_tier(scores[uid]["tier"])
            scores[uid]["score"] = 0
        scores[uid]["updated_at"] = datetime.now(timezone.utc).isoformat()

    for player in all_losers:
        uid = str(player.id)
        if not isinstance(scores.get(uid), dict):
            scores[uid] = {"score": 0, "tier": "4-1"}
        scores[uid]["score"] -= 1
        if scores[uid]["score"] <= -5:
            scores[uid]["tier"] = demote_tier(scores[uid]["tier"])
            scores[uid]["score"] = 0
        scores[uid]["updated_at"] = datetime.now(timezone.utc).isoformat()

    save_scores(scores)
    
    # 📜 Match log.json-д бүртгэх
    log_entry = {
        "mode": "3v3",  # ← энэ мөрийг нэм
        "winners": [str(m.id) for m in all_winners],
        "losers": [str(m.id) for m in all_losers],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        with open(LOG_FILE, "r") as f:
            log = json.load(f)
    except FileNotFoundError:
        log = []

    log.append(log_entry)
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

    changed_ids = [m.id for m in all_winners + all_losers]
    await update_nicknames_for_users(interaction.guild, changed_ids)

    winners_mentions = ", ".join([m.mention for m in all_winners])
    losers_mentions = ", ".join([m.mention for m in all_losers])

    await interaction.followup.send(
        f"🏆 Ялагчид: {winners_mentions} (+1)\n💔 Ялагдагчид: {losers_mentions} (-1)"
    )
# 🕹️ /undo_last_match — сүүлд хийсэн match-ийн оноог буцаана
@bot.tree.command(name="undo_last_match", description="Сүүлд хийсэн match-ийн оноог буцаана")
async def undo_last_match(interaction: discord.Interaction):
    try:
        with open(LAST_FILE, "r") as f:
            last = json.load(f)
    except FileNotFoundError:
        await interaction.response.send_message("⚠️ Сүүлд бүртгэсэн match олдсонгүй.")
        return

    scores = load_scores()
    changed_ids = []

    for uid in last.get("winners", []):
        if uid in scores:
            scores[uid]["score"] -= 1
            if scores[uid]["score"] < 0:
                scores[uid]["score"] = 0
            scores[uid]["updated_at"] = datetime.now(timezone.utc).isoformat()
            changed_ids.append(int(uid))
        
    for uid in last.get("losers", []):
        if uid in scores:
            scores[uid]["score"] += 1
            if scores[uid]["score"] > 5:
                scores[uid]["score"] = 5
            scores[uid]["updated_at"] = datetime.now(timezone.utc).isoformat()
            changed_ids.append(int(uid))
        

    save_scores(scores)
    await update_nicknames_for_users(interaction.guild, changed_ids)

    await interaction.response.send_message("↩️ Сүүлийн match-ийн оноо буцаагдлаа.")

@bot.tree.command(name="match_history", description="Сүүлийн тоглолтуудын жагсаалтыг харуулна")
async def match_history(interaction: discord.Interaction):
    try:
        with open(LOG_FILE, "r") as f:
            log = json.load(f)
    except FileNotFoundError:
        await interaction.response.send_message("📭 Match log хоосон байна.")
        return

    if not log:
        await interaction.response.send_message("📭 Match log хоосон байна.")
        return

    recent_matches = log[-5:]
    message = "📜 **Сүүлийн Match-ууд:**\n"

    for i, entry in enumerate(reversed(recent_matches), 1):
        winners = ", ".join(f"<@{uid}>" for uid in entry.get("winners", []))
        losers = ", ".join(f"<@{uid}>" for uid in entry.get("losers", []))
        mode = entry.get("mode", "unspecified")
        raw_ts = entry.get("timestamp")

        if raw_ts:
            try:
                dt = datetime.fromisoformat(raw_ts)
                dt_mn = dt.astimezone(timezone(timedelta(hours=8)))  # MGL timezone
                ts_str = dt_mn.strftime("%Y-%m-%d %H:%M")
            except:
                ts_str = raw_ts
        else:
            ts_str = "⏱️ цаггүй"

        message += f"\n**#{i} | {mode} | {ts_str}**\n🏆 {winners}\n💔 {losers}\n"

    await interaction.response.send_message(message)


@bot.tree.command(name="my_score", description="Таны оноог шалгах")
async def my_score(interaction: discord.Interaction):
    scores = load_scores()
    user_id = str(interaction.user.id)
    data = scores.get(user_id)

    if isinstance(data, dict):
        score = data.get("score", 0)
        tier = data.get("tier", "4-1")
        updated = data.get("updated_at")

        msg = f"📿 {interaction.user.mention} таны оноо: {score}\n🎖 Түвшин: **{tier}**"
        if updated:
            try:
                dt = datetime.fromisoformat(updated)
                formatted = dt.strftime("%Y-%m-%d %H:%M")
                msg += f"\n🕓 Сүүлд шинэчлэгдсэн: `{formatted}`"
            except:
                msg += f"\n🕓 Сүүлд шинэчлэгдсэн: `{updated}`"

        await interaction.response.send_message(msg)
    else:
        await interaction.response.send_message(
            f"📿 {interaction.user.mention} танд оноо бүртгэгдээгүй байна.\n🎖 Түвшин: **Tier-гүй байна**")

@bot.tree.command(name="scoreboard", description="Бүх тоглогчдын онооны жагсаалт")
async def scoreboard(interaction: discord.Interaction):
    # ✅ Админ эрх шалгах
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    scores = load_scores()

    # 🕓 Сүүлд шинэчлэгдсэн огноо олох
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
            if updated:
                try:
                    ts = datetime.fromisoformat(updated).strftime("%Y-%m-%d %H:%M")
                    update_str = f" (🕓 {ts})"
                except:
                    update_str = ""
            else:
                update_str = ""

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


@bot.tree.command(
    name="reset_scores",
    description="Бүх тоглогчийн оноог 0 болгоно (tier өөрчлөхгүй)"
)
async def reset_scores(interaction: discord.Interaction):
    # ✅ зөвхөн админ хэрэглэгч ажиллуулна
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.",
            ephemeral=True
        )
        return

    scores = load_scores()
    for user_id in scores:
        if isinstance(scores[user_id], dict):
            scores[user_id] = {
                "score": 0,
                "tier": scores[user_id].get("tier", "4-1")
            }
        else:
            scores[user_id] = {"score": 0, "tier": "4-1"}

    save_scores(scores)
    await interaction.response.send_message(
        "♻️ Бүх оноо амжилттай 0 боллоо (tier өөрчлөхгүй)."
    )

@bot.tree.command(
    name="reset_tier",
    description="Бүх тоглогчийн түвшинг 4-1 болгож, оноог 0 болгоно"
)
async def reset_tier(interaction: discord.Interaction):
    # ✅ зөвхөн админ хэрэглэгч ажиллуулна
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.",
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

    scores = load_scores()
    for user_id in scores:
        scores[user_id] = {"score": 0, "tier": "4-1"}
    save_scores(scores)
    await update_all_nicknames(interaction.guild)

    await interaction.followup.send(
        "🔁 Бүх түвшин 4-1 болгож, оноог 0 болголоо."
    )

@bot.tree.command(name="user_tier", description="Хэрэглэгчийн түвшинг харуулна")
@app_commands.describe(member="Түвшин шалгах хэрэглэгч")
async def user_tier(interaction: discord.Interaction, member: discord.Member):
    scores = load_scores()
    user_id = str(member.id)
    data = scores.get(user_id)

    if isinstance(data, dict):
        tier = data.get("tier", "4-1")
        await interaction.response.send_message(
            f"🎖 {member.mention} хэрэглэгчийн түвшин: **{tier}**"
        )
    else:
        await interaction.response.send_message(
            f"⚠️ {member.mention} хэрэглэгчид оноо/төвшин бүртгэгдээгүй байна."
        )
TEAM_SETUP = {
    "initiator_id": None,
    "team_count": 0,
    "players_per_team": 0,
    "player_ids": []
}

@bot.tree.command(name="make_team",
                  description="Тоглох багийн тохиргоог эхлүүлнэ")
@app_commands.describe(team_count="Хэдэн багтай байх вэ",
                       players_per_team="Нэг багт хэдэн хүн байх вэ")
async def make_team(interaction: discord.Interaction, team_count: int,
                    players_per_team: int):
    TEAM_SETUP["initiator_id"] = interaction.user.id
    TEAM_SETUP["team_count"] = team_count
    TEAM_SETUP["players_per_team"] = players_per_team
    TEAM_SETUP["player_ids"] = []

    await interaction.response.send_message(
        f"🎯 Багийн тохиргоо эхэллээ! Нийт {team_count} баг, нэг багт {players_per_team} хүн байна. "
        f"Тоглогчид /addme гэж бүртгүүлнэ үү.\n"
        f"⏳ **5 минутын дараа автоматаар баг хуваарилна.**")

    # Таймер асаана
    async def auto_assign():
        await asyncio.sleep(300)  # 5 минут
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
    if TEAM_SETUP["initiator_id"] is None:
        await interaction.response.send_message("⚠️ /make_team командаар эхлүүлсний дараа /addme ашиглана уу.")
        return

    user_id = interaction.user.id
    if user_id not in TEAM_SETUP["player_ids"]:
        TEAM_SETUP["player_ids"].append(user_id)
        all_players = ", ".join([f"<@{uid}>" for uid in TEAM_SETUP["player_ids"]])
        await interaction.response.send_message(
            f"✅ {interaction.user.mention} амжилттай бүртгэгдлээ!\n"
            f"📋 Бүртгэгдсэн тоглогчид: {all_players}"
        )
    else:
        await interaction.response.send_message(
            "⚠️ Та аль хэдийн бүртгэгдсэн байна."
        )



@bot.tree.command(name="make_team_go", description="Бүртгүүлсэн тоглогчдыг багт хуваана")
async def make_team_go(interaction: discord.Interaction):
    if interaction.user.id != TEAM_SETUP["initiator_id"]:
        await interaction.response.send_message("❌ Зөвхөн тохиргоог эхлүүлсэн хүн баг хуваарилалтыг эхлүүлж болно.")
        return

    await interaction.response.defer(thinking=True)

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
        tier = data.get("tier", "4-1")
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

    now = datetime.utcnow()
    GAME_SESSION["active"] = True
    GAME_SESSION["start_time"] = now
    GAME_SESSION["last_win_time"] = now

    # 🗃️ Багийн бүрэлдэхүүнийг log файлд хадгалах
    log_data = {
        "timestamp": now.isoformat(),
        "teams": team_ids
    }
    with open("team_log.json", "w") as f:
        json.dump(log_data, f, indent=4)


# 🏆 Winner Team сонгох
@bot.tree.command(name="set_winner_team", description="Хожсон болон хожигдсон багийг зааж оноо өгнө")
@app_commands.describe(
    winning_team="Хожсон багийн дугаар (1, 2, 3...)",
    losing_team="Хожигдсон багийн дугаар (1, 2, 3...)"
)
async def set_winner_team(interaction: discord.Interaction, winning_team: int, losing_team: int):
    # Зөвхөн эхлүүлэгч ажиллуулах эрхтэй эсэхийг шалгах
    if interaction.user.id != TEAM_SETUP.get("initiator_id"):
        await interaction.response.send_message("❌ Зөвхөн багийн тохиргоог эхлүүлсэн хүн энэ командыг ажиллуулж чадна.", ephemeral=True)
        return

    if not GAME_SESSION["active"]:
        await interaction.response.send_message("⚠️ Session идэвхгүй байна. /make_team_go-оор эхлүүлнэ үү.")
        return

    team_count = TEAM_SETUP["team_count"]
    team_size = TEAM_SETUP["players_per_team"]

    if not (1 <= winning_team <= team_count) or not (1 <= losing_team <= team_count):
        await interaction.response.send_message("❌ Ийм багийн дугаар байхгүй байна.")
        return

    if winning_team == losing_team:
        await interaction.response.send_message("⚠️ Хожсон ба хожигдсон баг адил байна!")
        return

    await interaction.response.defer(thinking=True)

    def get_team_user_ids(team_number):
        start_idx = (team_number - 1) * team_size
        end_idx = start_idx + team_size
        return TEAM_SETUP["player_ids"][start_idx:end_idx]

    scores = load_scores()
    shields = load_shields()
    guild = interaction.guild
    changed_ids = []

    winning_user_ids = get_team_user_ids(winning_team)
    losing_user_ids = get_team_user_ids(losing_team)

    winners, losers = [], []

    # 🏆 Хожсон баг оноо нэмнэ
    for uid in winning_user_ids:
        uid_str = str(uid)
        member = guild.get_member(uid)
        if uid_str not in scores:
            scores[uid_str] = {"score": 0, "tier": "4-1"}
        scores[uid_str]["score"] += 1
        if scores[uid_str]["score"] >= 5:
            scores[uid_str]["tier"] = promote_tier(scores[uid_str]["tier"])
            scores[uid_str]["score"] = 0
        scores[uid_str]["updated_at"] = datetime.now(timezone.utc).isoformat()
        changed_ids.append(uid)
        if member:
            winners.append(member.mention)

    # 💔 Хожигдсон баг — Shield шалгаад оноо хасна
    for uid in losing_user_ids:
        uid_str = str(uid)
        member = guild.get_member(uid)
        if uid_str not in scores:
            scores[uid_str] = {"score": 0, "tier": "4-1"}
        if await should_deduct(uid_str, shields):
            scores[uid_str]["score"] -= 1
            if scores[uid_str]["score"] <= -5:
                scores[uid_str]["tier"] = demote_tier(scores[uid_str]["tier"])
                scores[uid_str]["score"] = 0
        scores[uid_str]["updated_at"] = datetime.now(timezone.utc).isoformat()
        changed_ids.append(uid)
        if member:
            losers.append(member.mention)

    save_scores(scores)
    save_shields(shields)
    await update_nicknames_for_users(guild, changed_ids)

    # 📝 Match log бүртгэх
    log_entry = {
        "mode": "set_team",  # ← энэ command-ын төрөл
        "winners": [str(uid) for uid in winning_user_ids],
        "losers": [str(uid) for uid in losing_user_ids],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        with open(LOG_FILE, "r") as f:
            log = json.load(f)
    except FileNotFoundError:
        log = []

    log.append(log_entry)
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

    await interaction.followup.send(f"🏆 Team {winning_team}-ийн гишүүд оноо авлаа: ✅ +1\n{', '.join(winners)}")
    await interaction.followup.send(f"💔 Team {losing_team}-ийн гишүүд оноо хасагдлаа: ❌ -1\n{', '.join(losers)}")

    GAME_SESSION["last_win_time"] = datetime.utcnow()


# 🔄 Тоглогч солих
@bot.tree.command(name="change_player", description="Багт тоглогч солих")
@app_commands.describe(from_member="Солигдох тоглогч", to_member="Шинэ тоглогч")
async def change_player(interaction: discord.Interaction, from_member: discord.Member, to_member: discord.Member):
    # Зөвхөн эхлүүлэгч ажиллуулах эрхтэй эсэх шалгах
    if interaction.user.id != TEAM_SETUP.get("initiator_id"):
        await interaction.response.send_message("❌ Зөвхөн багийн тохиргоог эхлүүлсэн хүн энэ командыг ажиллуулж чадна.", ephemeral=True)
        return

    user_ids = TEAM_SETUP["player_ids"]
    players_per_team = TEAM_SETUP["players_per_team"]
    team_count = TEAM_SETUP["team_count"]

    if from_member.id not in user_ids:
        await interaction.response.send_message(f"⚠️ {from_member.mention} багт бүртгэгдээгүй байна.")
        return

    if to_member.id in user_ids:
        await interaction.response.send_message(f"⚠️ {to_member.mention} аль хэдийн өөр багт бүртгэгдсэн байна.")
        return

    idx = user_ids.index(from_member.id)
    TEAM_SETUP["player_ids"][idx] = to_member.id

    old_team = (idx // players_per_team) + 1  # Багийн дугаар (1-с эхэлнэ)

    await interaction.response.send_message(
        f"🔁 {from_member.mention} → {to_member.mention} солигдлоо!\n"
        f"📌 {from_member.mention} нь Team {old_team}-д байсан."
    )




def load_shields():
    if not os.path.exists(SHIELD_FILE):
        return {}
    with open(SHIELD_FILE, "r") as f:
        return json.load(f)

def save_shields(data):
    with open(SHIELD_FILE, "w") as f:
        json.dump(data, f, indent=4)

@bot.tree.command(name="donate_shield", description="Тоглогчид хамгаалалтын удаа онооно")
@app_commands.describe(
    member="Хамгаалалт авах тоглогч",
    count="Хэдэн удаа хамгаалах вэ (default: 1)"
)
async def donate_shield(interaction: discord.Interaction, member: discord.Member, count: int = 1):
    # ✅ Зөвхөн админ хэрэглэгч шалгах
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.",
            ephemeral=True
        )
        return

    if count <= 0:
        await interaction.response.send_message("⚠️ Хамгаалалтын тоо 1-с дээш байх ёстой.")
        return

    shields = load_shields()
    uid = str(member.id)
    shields[uid] = shields.get(uid, 0) + count
    save_shields(shields)

    await interaction.response.send_message(
        f"🛡️ {member.mention} хэрэглэгчид {count} удаагийн хамгаалалт амжилттай өглөө!"
    )

@bot.tree.command(name="init_scores",
                  description="Бүх гишүүдэд default оноо, tier (4-1) онооно")
async def init_scores(interaction: discord.Interaction):
    # ✅ зөвхөн админ хэрэглэгч ажиллуулна
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.",
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

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
    # ✅ зөвхөн админ эрхтэй хэрэглэгч ажиллуулна
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.", ephemeral=True)
        return

    if new_tier not in TIER_ORDER:
        await interaction.response.send_message(f"❌ Tier: `{new_tier}` олдсонгүй. Зөвхөн дараах байдлаар байна:\n{', '.join(TIER_ORDER)}", ephemeral=True)
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
        await interaction.response.send_message("⚠️ Tier амжилттай солигдсон ч nickname өөрчилж чадсангүй (permission issue).", ephemeral=True)
        return
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Алдаа гарлаа: {e}", ephemeral=True)
        return

    await interaction.response.send_message(f"✅ {member.mention}-ийн tier-г `{new_tier}` болголоо.")


@bot.tree.command(name="delete_tier",
                  description="Бүх гишүүний оноо ба tier-г бүрэн устгана")
async def delete_tier(interaction: discord.Interaction):
    # ✅ зөвхөн админ хэрэглэгч ажиллуулна
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.",
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

    # Оноо, түвшин бүгдийг арилгана
    save_scores({})  # scores.json-г хоослоно

    guild = interaction.guild
    removed_lines = []
    for member in guild.members:
        if member.bot:
            continue
        try:
            base_nick = member.nick or member.name
            for prefix in TIER_ORDER:
                if base_nick.startswith(f"{prefix} |"):
                    base_nick = base_nick[len(prefix) + 2:].strip()
                    await member.edit(nick=base_nick)
                    removed_lines.append(
                        f"🧹 {member.display_name} → {base_nick}")
        except discord.Forbidden:
            removed_lines.append(
                f"⛔️ {member.display_name} nickname-г өөрчилж чадсангүй")
        except Exception as e:
            removed_lines.append(
                f"⚠️ {member.display_name} nickname-д алдаа гарлаа")

    # Мессеж тасдаж илгээнэ
    if removed_lines:
        chunk = "🧹 **Түвшин nickname устгалт:**\n"
        for line in removed_lines:
            if len(chunk) + len(line) + 1 > 1900:
                await interaction.followup.send(chunk)
                chunk = ""
            chunk += line + "\n"
        if chunk:
            await interaction.followup.send(chunk)
    else:
        await interaction.followup.send(
            "✅ Оноо устсан. Түвшинтэй nickname олдсонгүй.")


@bot.tree.command(name="user_score", description="Хэрэглэгчийн оноо болон түвшинг харуулна")
@app_commands.describe(member="Оноог шалгах хэрэглэгч")
async def user_score(interaction: discord.Interaction, member: discord.Member):
    scores = load_scores()
    user_id = str(member.id)
    data = scores.get(user_id)

    if isinstance(data, dict):
        score = data.get("score", 0)
        tier = data.get("tier", "4-1")
        await interaction.response.send_message(
            f"👤 {member.mention} хэрэглэгчийн оноо: {score}\n🎖 Түвшин: **{tier}**"
        )
    else:
        await interaction.response.send_message(
            f"👤 {member.mention} хэрэглэгчид оноо бүртгэгдээгүй байна."
        )

@bot.tree.command(name="match2", description="2v2 match result")
@app_commands.describe(winner1="Ялагч 1", winner2="Ялагч 2",
                       loser1="Ялагдагч 1", loser2="Ялагдагч 2")
async def match2(interaction: discord.Interaction,
                 winner1: discord.Member, winner2: discord.Member,
                 loser1: discord.Member, loser2: discord.Member):

    await interaction.response.defer(thinking=True)

    all_winners = [winner1, winner2]
    all_losers = [loser1, loser2]

    if len(set(all_winners + all_losers)) < 4:
        await interaction.followup.send("❌ Тоглогчид давхцаж байна!")
        return

    scores = load_scores()

    for player in all_winners:
        uid = str(player.id)
        if not isinstance(scores.get(uid), dict):
            scores[uid] = {"score": 0, "tier": "4-1"}
        scores[uid]["score"] += 1
        if scores[uid]["score"] >= 5:
            scores[uid]["tier"] = promote_tier(scores[uid]["tier"])
            scores[uid]["score"] = 0
        scores[uid]["updated_at"] = datetime.now(timezone.utc).isoformat()

    for player in all_losers:
        uid = str(player.id)
        if not isinstance(scores.get(uid), dict):
            scores[uid] = {"score": 0, "tier": "4-1"}
        scores[uid]["score"] -= 1
        if scores[uid]["score"] <= -5:
            scores[uid]["tier"] = demote_tier(scores[uid]["tier"])
            scores[uid]["score"] = 0
        scores[uid]["updated_at"] = datetime.now(timezone.utc).isoformat()

    save_scores(scores)

    # log.json-д хадгалах
    log_entry = {
        "mode": "2v2",  # ← энэ мөрийг нэм
        "winners": [str(m.id) for m in all_winners],
        "losers": [str(m.id) for m in all_losers],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        with open(LOG_FILE, "r") as f:
            log = json.load(f)
    except FileNotFoundError:
        log = []

    log.append(log_entry)
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

    # last_match.json-д хадгалах
    with open(LAST_FILE, "w") as f:
        json.dump(log_entry, f, indent=2)

    changed_ids = [m.id for m in all_winners + all_losers]
    await update_nicknames_for_users(interaction.guild, changed_ids)

    winners_mentions = ", ".join([m.mention for m in all_winners])
    losers_mentions = ", ".join([m.mention for m in all_losers])

    await interaction.followup.send(
        f"🏆 Ялагчид: {winners_mentions} (+1)\n💔 Ялагдагчид: {losers_mentions} (-1)"
    )

@bot.tree.command(name="set_winner_team_fountain", description="Fountain дээр хожсон ба хожигдсон багуудад оноо өгнө")
@app_commands.describe(
    winning_team="Хожсон багийн дугаар (1, 2, 3...)",
    losing_team="Хожигдсон багийн дугаар (1, 2, 3...)"
)
async def set_winner_team_fountain(interaction: discord.Interaction, winning_team: int, losing_team: int):
    # Зөвхөн эхлүүлэгч ажиллуулах эрхтэй эсэхийг шалгах
    if interaction.user.id != TEAM_SETUP.get("initiator_id"):
        await interaction.response.send_message("❌ Зөвхөн багийн тохиргоог эхлүүлсэн хүн энэ командыг ажиллуулж чадна.", ephemeral=True)
        return

    if not GAME_SESSION["active"]:
        await interaction.response.send_message("⚠️ Session идэвхгүй байна. /make_team_go-оор эхлүүлнэ үү.")
        return

    if winning_team < 1 or winning_team > TEAM_SETUP["team_count"] or losing_team < 1 or losing_team > TEAM_SETUP["team_count"]:
        await interaction.response.send_message("❌ Багийн дугаар буруу байна.")
        return

    await interaction.response.defer(thinking=True)

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
        if uid_str not in scores:
            scores[uid_str] = {"score": 0, "tier": "4-1"}
        scores[uid_str]["score"] += 2
        while scores[uid_str]["score"] >= 5:
            scores[uid_str]["tier"] = promote_tier(scores[uid_str]["tier"])
            scores[uid_str]["score"] -= 5
        scores[uid_str]["updated_at"] = datetime.now(timezone.utc).isoformat()
        changed_ids.append(uid)

    for uid in losing_ids:
        uid_str = str(uid)
        if uid_str not in scores:
            scores[uid_str] = {"score": 0, "tier": "4-1"}
        scores[uid_str]["score"] -= 2
        while scores[uid_str]["score"] <= -5:
            scores[uid_str]["tier"] = demote_tier(scores[uid_str]["tier"])
            scores[uid_str]["score"] += 5
        scores[uid_str]["updated_at"] = datetime.now(timezone.utc).isoformat()
        changed_ids.append(uid)

    save_scores(scores)
    await update_nicknames_for_users(guild, changed_ids)

    win_mentions = ", ".join([f"<@{uid}>" for uid in winning_ids])
    lose_mentions = ", ".join([f"<@{uid}>" for uid in losing_ids])

    # 📝 Match log бүртгэх
    log_entry = {
        "mode": "fountain",
        "winners": [str(uid) for uid in winning_ids],
        "losers": [str(uid) for uid in losing_ids],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        with open(LOG_FILE, "r") as f:
            log = json.load(f)
    except FileNotFoundError:
        log = []

    log.append(log_entry)
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

    await interaction.followup.send(
        f"🌊 **Fountain оноо өглөө!**\n"
        f"🏆 Хожсон баг (Team {winning_team}): {win_mentions} → **+2**\n"
        f"💔 Хожигдсон баг (Team {losing_team}): {lose_mentions} → **–2**"
    )

@bot.tree.command(name="active_teams", description="Идэвхтэй session-д бүртгэлтэй багуудыг харуулна")
async def active_teams(interaction: discord.Interaction):
    if not GAME_SESSION["active"]:
        await interaction.response.send_message("⚠️ Session идэвхгүй байна.")
        return

    team_count = TEAM_SETUP["team_count"]
    players_per_team = TEAM_SETUP["players_per_team"]
    user_ids = TEAM_SETUP["player_ids"]

    if not user_ids:
        await interaction.response.send_message("📭 Одоогоор бүртгэгдсэн багийн гишүүд алга.")
        return

    msg = f"📋 **Идэвхтэй багуудын жагсаалт:**\n"
    for i in range(team_count):
        start = i * players_per_team
        end = start + players_per_team
        team_members = user_ids[start:end]
        mentions = [f"<@{uid}>" for uid in team_members]
        msg += f"\n🏅 **Team {i+1}:** " + ", ".join(mentions)

    await interaction.response.send_message(msg)
@bot.tree.command(name="set_team", description="Админ: гараар багийн бүртгэл үүсгэнэ")
@app_commands.describe(
    team_count="Багийн тоо",
    players_per_team="Нэг багт хэдэн хүн байх",
    mentions="Тоглогчдыг mention-ээр оруулна (дарааллаар)"
)
async def set_team(interaction: discord.Interaction, team_count: int, players_per_team: int, mentions: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔️ Зөвхөн админ л ашиглана.", ephemeral=True)
        return

    user_ids = [word[2:-1].replace("!", "") for word in mentions.split() if word.startswith("<@") and word.endswith(">")]
    expected = team_count * players_per_team

    if len(user_ids) != expected:
        await interaction.response.send_message(
            f"⚠️ Нийт гишүүдийн тоо {expected}-той тэнцүү байх ёстой. ({team_count} баг × {players_per_team} хүн)",
            ephemeral=True
        )
        return

    TEAM_SETUP["initiator_id"] = interaction.user.id
    TEAM_SETUP["team_count"] = team_count
    TEAM_SETUP["players_per_team"] = players_per_team
    TEAM_SETUP["player_ids"] = [int(uid) for uid in user_ids]

    GAME_SESSION["active"] = True
    now = datetime.utcnow()
    GAME_SESSION["start_time"] = now
    GAME_SESSION["last_win_time"] = now

    msg = "✅ Гараар баг бүртгэл амжилттай!\n"
    for i in range(team_count):
        start = i * players_per_team
        end = start + players_per_team
        team = user_ids[start:end]
        mentions = [f"<@{uid}>" for uid in team]
        msg += f"\n🏅 **Team {i+1}:** " + ", ".join(mentions)

    await interaction.response.send_message(msg)


@bot.tree.command(name="add_team", description="Шинэ багийг тоглож буй session-д нэмнэ")
@app_commands.describe(
    mentions="Шинэ багийн гишүүдийн mention-ууд"
)
async def add_team(interaction: discord.Interaction, mentions: str):
    # Зөвхөн session эхлүүлэгч ашиглах эрхтэй эсэхийг шалгах
    if interaction.user.id != TEAM_SETUP.get("initiator_id"):
        await interaction.response.send_message("❌ Зөвхөн багийн тохиргоог эхлүүлсэн хүн энэ командыг ашиглах эрхтэй.", ephemeral=True)
        return

    if not GAME_SESSION["active"]:
        await interaction.response.send_message("⚠️ Session идэвхгүй байна. /make_team_go-оор эхлүүлнэ үү.")
        return

    await interaction.response.defer(thinking=True)

    user_ids = [word[2:-1].replace("!", "") for word in mentions.split() if word.startswith("<@") and word.endswith(">")]
    if len(user_ids) != TEAM_SETUP["players_per_team"]:
        await interaction.followup.send(
            f"⚠️ Шинээр багт бүртгэх гишүүдийн тоо {TEAM_SETUP['players_per_team']}-тэй яг тэнцүү байх ёстой.")
        return

    # Давхцсан тоглогч шалгах
    already_in = [uid for uid in user_ids if int(uid) in TEAM_SETUP["player_ids"]]
    if already_in:
        mention_list = ", ".join([f"<@{uid}>" for uid in already_in])
        await interaction.followup.send(f"⚠️ Дараах тоглогчид аль хэдийн багт бүртгэгдсэн байна: {mention_list}")
        return

    # Шинэ гишүүдийг нэмэх
    TEAM_SETUP["player_ids"].extend([int(uid) for uid in user_ids])
    TEAM_SETUP["team_count"] += 1  # шинэ баг нэмсэн тул багийн тоо өснө

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
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.", ephemeral=True)
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

    # 🎖 emoji logic → total_mnt дээр суурилна
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
        await interaction.response.send_message("⚠️ Donator болгосон ч nickname өөрчилж чадсангүй (permission issue).", ephemeral=True)
        return

    await interaction.response.send_message(
        f"{emoji} {member.mention} хэрэглэгчийг Donator болголоо! (нийт {total_mnt:,}₮)"
    )

@bot.tree.command(name="donator_list", description="Donator хэрэглэгчдийн жагсаалт")
async def donator_list(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Энэ командыг зөвхөн админ хэрэглэгч ашиглаж болно.", ephemeral=True)
        return

    donors = load_donators()
    if not donors:
        await interaction.response.send_message("📭 Donator бүртгэл алга байна.")
        return

    msg = "💖 **Donators:**\n"
    sorted_donors = sorted(donors.items(), key=lambda x: x[1].get("total_mnt", 0), reverse=True)

    for uid, data in sorted_donors:
        member = interaction.guild.get_member(int(uid))
        if member:
            emoji = get_donator_emoji(data)
            total = data.get("total_mnt", 0)
            if emoji:
                new_nick = f"{emoji} {get_tier} | {member.display_name}"
            else:
                new_nick = f"{get_tier} | {member.display_name}"
            
            msg += f"{emoji} {member.display_name} — {total:,}₮\n"

    await interaction.response.send_message(msg)

async def should_deduct(uid_str: str, shields: dict) -> bool:
    if shields.get(uid_str, 0) > 0:
        shields[uid_str] -= 1
        if shields[uid_str] <= 0:
            shields.pop(uid_str)
        save_shields(shields)
        return False
    return True

@bot.tree.command(name="all_commands", description="Ботод бүртгэлтэй бүх / командуудыг харуулна")
async def all_commands(interaction: discord.Interaction):
    # ✅ Админ эрх шалгана
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)  # 🧠 Discord-д 'Bot is thinking...' илгээнэ

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
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Энэ командыг зөвхөн админ хэрэглэгч ажиллуулж чадна.",
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)  # ⏳ Discord-д хариу илгээж, timeout-оос сэргийлнэ

    user_ids = [word[2:-1].replace("!", "") for word in mentions.split() if word.startswith("<@") and word.endswith(">")]

    if not user_ids:
        await interaction.followup.send("⚠️ Хэрэглэгчийн mention оруулна уу.")
        return

    scores = load_scores()
    updated = []
    failed = []

    for uid in user_ids:
        try:
            member = await interaction.guild.fetch_member(int(uid))
        except Exception as e:
            print(f"❌ {uid} fetch алдаа: {e}")
            failed.append(uid)
            continue

        if uid not in scores:
            scores[uid] = {"score": 0, "tier": "4-1"}

        scores[uid]["score"] += points

        while scores[uid]["score"] >= 5:
            scores[uid]["tier"] = promote_tier(scores[uid]["tier"])
            scores[uid]["score"] -= 5
        
        while scores[uid]["score"] <= -5:
            scores[uid]["tier"] = demote_tier(scores[uid]["tier"])
            scores[uid]["score"] += 5
        scores[uid]["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated.append(member)

    print(f"[add_score] {member.name} оноо: {scores[uid]['score']}, tier: {scores[uid]['tier']}")


    save_scores(scores)

    if updated:
        await update_nicknames_for_users(interaction.guild, [m.id for m in updated])

    msg = f"✅ Оноо `{points}`-оор шинэчлэгдсэн гишүүд:\n" + "\n".join(f"• {m.mention}" for m in updated)
    if failed:
        msg += f"\n⚠️ Дараах ID-г хөрвүүлж чадсангүй: {', '.join(failed)}"

    await interaction.followup.send(msg)
   
# ⏱️ Session хугацаа дууссан эсэх шалгагч task
async def session_timeout_checker():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(60)  # 1 минут тутамд шалгана
        if GAME_SESSION["active"]:
            now = datetime.utcnow()
            elapsed = now - GAME_SESSION["last_win_time"]
            if elapsed.total_seconds() > 86400:  # 24 цаг = 86400 секунд
                GAME_SESSION["active"] = False
                GAME_SESSION["start_time"] = None
                GAME_SESSION["last_win_time"] = None
                print("🔚 Session автоматаар хаагдлаа (24 цаг өнгөрсөн).")

@bot.tree.command(name="resync", description="Slash командуудыг дахин сервертэй sync хийнэ (зөвхөн админд)")
async def resync(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔️ Зөвхөн админ л ашиглана.", ephemeral=True)
        return

    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("⚠️ Энэ командыг зөвхөн сервер дээр ажиллуулна уу.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)  # ← Discord-д "bot is thinking..." илгээнэ

    bot.tree.copy_global_to(guild=guild)  # await ХЭРЭГГҮЙ
    await bot.tree.sync(guild=guild)

    await interaction.followup.send(f"✅ Командууд `{guild.name}` сервер дээр дахин sync хийгдлээ.")

@bot.event
async def on_ready():
    print(f"🤖 Bot logged in as {bot.user}")
    print("📁 Working directory:", os.getcwd())

    for guild in bot.guilds:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced commands for guild: {guild.name} ({guild.id})")

    asyncio.create_task(session_timeout_checker())

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
