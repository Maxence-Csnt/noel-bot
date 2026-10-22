import os
import json
import copy
import random
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Paris")
except Exception:  # tzdata absent : on retombe sur UTC+1
    TZ = timezone(timedelta(hours=1))

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
DATA_FILE = Path(__file__).with_name("frosty_data.json")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

GREEN = 0x16804A
RED = 0xC62828
GOLD = 0xF6C453

SHOP = {
    "bonnet": {"name": "Bonnet d'elfe", "price": 100, "emoji": "🧝"},
    "canne": {"name": "Canne en sucre", "price": 250, "emoji": "🍬"},
    "sapin": {"name": "Mini sapin", "price": 400, "emoji": "🎄"},
    "bonhomme": {"name": "Bonhomme de neige", "price": 500, "emoji": "⛄"},
    "traineau": {"name": "Traîneau doré", "price": 750, "emoji": "🛷"},
    "etoile": {"name": "Étoile du sapin", "price": 1000, "emoji": "⭐"},
    "renne": {"name": "Renne Rudolph", "price": 1500, "emoji": "🦌"},
}
SHOP_CHOICES = [
    app_commands.Choice(name=f"{i['name']} — {i['price']} flocons", value=k)
    for k, i in SHOP.items()
]

QUIZ = [
    ("Quel pays a popularisé le sapin de Noël décoré ?", "L'Allemagne", ["La Suède", "L'Espagne", "L'Italie"]),
    ("Combien de rennes tirent le traîneau dans « La Nuit d'avant Noël » ?", "8", ["6", "9", "12"]),
    ("Quel dessert est traditionnel pour le réveillon en France ?", "La bûche", ["La galette", "Le Paris-Brest", "La tarte Tatin"]),
    ("Sous quelle plante s'embrasse-t-on à Noël ?", "Le gui", ["Le houx", "Le lierre", "Le laurier"]),
    ("Dans quel pays se trouve le village du Père Noël à Rovaniemi ?", "La Finlande", ["La Norvège", "Le Canada", "L'Islande"]),
    ("Comment s'appelle le renne au nez rouge ?", "Rudolph", ["Comet", "Cupidon", "Prancer"]),
    ("Quel conte de Dickens met en scène Ebenezer Scrooge ?", "Un chant de Noël", ["Oliver Twist", "David Copperfield", "De grandes espérances"]),
    ("Quel film met en scène Kevin McCallister, oublié seul à la maison ?", "Maman, j'ai raté l'avion", ["Le Grinch", "Elfe", "Polar Express"]),
    ("Combien de bougies compte la couronne de l'Avent traditionnelle ?", "4", ["3", "5", "7"]),
    ("Quel ballet de Tchaïkovski est associé à Noël ?", "Casse-Noisette", ["Le Lac des cygnes", "La Belle au bois dormant", "Roméo et Juliette"]),
]

JOKES = [
    "Pourquoi le Père Noël a-t-il trois jardins ? Pour pouvoir faire Ho Ho Ho ! 🎅",
    "Comment appelle-t-on un bonhomme de neige en été ? Une flaque ! 💧",
    "Qu'est-ce qui est vert, qui pique et qu'on trouve dans le salon ? Un sapin… ou un cactus qui s'est trompé de fête ! 🌵",
    "Quel est le comble pour un lutin ? Travailler comme un elfe… et être payé en flocons ! ❄️",
    "Pourquoi le sapin déteste-t-il janvier ? Il perd ses aiguilles et finit sur le trottoir ! 🎄",
]

GIFT_IDEAS = [
    "Un plaid ultra doux 🧣", "Un livre de recettes de cookies 🍪", "Un jeu de société pour les soirées d'hiver 🎲",
    "Une bougie parfumée à la cannelle 🕯️", "Un calendrier de l'Avent chocolaté 🍫", "Un pull de Noël moche mais culte 🎅",
    "Un mug avec un chocolat chaud et des marshmallows ☕", "Une prise connectée pour les guirlandes 💡",
    "Un puzzle de 1000 pièces 🧩", "Un bon pour une soirée film de Noël 🎬",
]

music_queues = {}

DEFAULT_USER = {
    "coins": 0,
    "last_daily": None,
    "last_gift": None,
    "inventory": [],
    "streak": 0,
    "advent": [],
    "wishlist": [],
    "quiz_day": None,
    "quiz_count": 0,
}


# ───────────────────────── Données ─────────────────────────

def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"users": {}, "events": {}}


data = load_data()


def save_data():
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA_FILE)


def get_user(user_id: int):
    user = data["users"].setdefault(str(user_id), {})
    for key, value in DEFAULT_USER.items():
        if key not in user:
            user[key] = copy.deepcopy(value)
    return user


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", "\u202f")


def embed(title: str, description: str, color: int = GREEN):
    e = discord.Embed(title=f"🎄 {title}", description=description, color=color)
    e.set_footer(text="Frosty • L'esprit de Noël toute l'année")
    return e


def esc(text: str) -> str:
    return discord.utils.escape_markdown(text)


def parse_date(text: str):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


def cooldown_text(last_value):
    if not last_value:
        return None
    last = datetime.fromisoformat(last_value)
    remaining = timedelta(hours=24) - (datetime.now(timezone.utc) - last)
    if remaining.total_seconds() <= 0:
        return None
    hours, rem = divmod(int(remaining.total_seconds()), 3600)
    minutes = rem // 60
    return f"Reviens dans **{hours} h {minutes} min** pour ton prochain cadeau. 🎁"


def next_christmas():
    now = datetime.now(TZ)
    xmas = datetime(now.year, 12, 25, tzinfo=TZ)
    if now >= xmas + timedelta(days=1):
        xmas = datetime(now.year + 1, 12, 25, tzinfo=TZ)
    return now, xmas


# ───────────────────────── Musique ─────────────────────────

async def get_music_info(url: str):
    if yt_dlp is None:
        raise RuntimeError("Installe yt-dlp avec `pip install yt-dlp`.")
    opts = {"format": "bestaudio/best", "quiet": True, "no_warnings": True, "noplaylist": True}
    loop = asyncio.get_running_loop()

    def extract():
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    info = await loop.run_in_executor(None, extract)
    if "entries" in info:
        info = next((item for item in info["entries"] if item), None)
    if not info:
        raise RuntimeError("Impossible de trouver cette piste.")
    return {"title": info.get("title", "Piste sans titre"), "url": info.get("webpage_url", url),
            "stream_url": info.get("url")}


async def play_next(guild_id: int):
    queue = music_queues.get(guild_id)
    if not queue:
        return
    if queue.get("loop") and queue.get("current"):
        queue["songs"].append(queue["current"])
    if not queue["songs"]:
        queue["current"] = None
        return

    song = queue["songs"].pop(0)
    queue["current"] = song
    try:
        # Les liens de streaming expirent : on les rafraîchit avant la lecture
        try:
            fresh = await get_music_info(song["url"])
            song["stream_url"] = fresh["stream_url"]
        except Exception:
            pass
        source = discord.FFmpegPCMAudio(
            song["stream_url"],
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn",
        )
        source = discord.PCMVolumeTransformer(source, volume=queue.get("volume", 0.35))
        queue["source"] = source

        def after_play(error):
            if error:
                print(f"Erreur audio : {error}")
            future = asyncio.run_coroutine_threadsafe(play_next(guild_id), bot.loop)
            try:
                future.result()
            except Exception as exc:
                print(f"Erreur file musicale : {exc}")

        queue["voice"].play(source, after=after_play)
        channel = queue.get("text_channel")
        if channel:
            await channel.send(embed=embed("À l'écoute 🎶", f"**{esc(song['title'])}**\nAjouté par {song['requester']}"))
    except Exception as exc:
        print(f"Impossible de lire la piste : {exc}")
        queue["current"] = None
        channel = queue.get("text_channel")
        if channel:
            await channel.send(embed=embed("Petit couac musical", "Impossible de lire cette piste. Je passe à la suivante.", RED))
        await play_next(guild_id)


# ───────────────────────── Événements du bot ─────────────────────────

@bot.event
async def on_ready():
    try:
        if GUILD_ID:
            guild_obj = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild_obj)
            synced = await bot.tree.sync(guild=guild_obj)
        else:
            synced = await bot.tree.sync()
        print(f"🎅 Frosty est connecté en tant que {bot.user} — {len(synced)} commandes synchronisées.")
    except Exception as exc:
        print(f"Erreur de synchronisation des commandes : {exc}")
    if not event_reminder.is_running():
        event_reminder.start()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"Doucement ! Réessaie dans **{error.retry_after:.0f} s** ⏳"
    else:
        print(f"Erreur commande : {error!r}")
        msg = "Oups, un lutin a renversé la hotte… Réessaie dans un instant 🎁"
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


@bot.event
async def on_voice_state_update(member, before, after):
    """Quitte le vocal si plus personne (hors bots) n'est présent."""
    voice = member.guild.voice_client
    if not voice or not voice.channel:
        return
    if any(not m.bot for m in voice.channel.members):
        return
    music_queues.pop(member.guild.id, None)
    if voice.is_playing() or voice.is_paused():
        voice.stop()
    await voice.disconnect(force=True)


@tasks.loop(minutes=1)
async def event_reminder():
    now = datetime.now(timezone.utc)
    changed = False
    for event_id, e in list(data["events"].items()):
        when = datetime.fromisoformat(e["date"])
        if when < now - timedelta(hours=1):
            del data["events"][event_id]
            changed = True
            continue
        if not e.get("notified") and when - now <= timedelta(minutes=15):
            channel = bot.get_channel(e.get("channel_id") or 0)
            if channel:
                try:
                    await channel.send(embed=embed(
                        "Ça commence bientôt !",
                        f"**{esc(e['name'])}** démarre <t:{int(when.timestamp())}:R> 🎉\n{esc(e['description'])}",
                        GOLD,
                    ))
                except discord.HTTPException:
                    pass
            e["notified"] = True
            changed = True
    if changed:
        save_data()


# ───────────────────────── Économie ─────────────────────────

@bot.tree.command(name="cadeau", description="Ouvre ton cadeau de Noël quotidien")
async def cadeau(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Utilise cette commande dans un serveur 🎁", ephemeral=True)
    user = get_user(interaction.user.id)
    now = datetime.now(timezone.utc)
    msg = cooldown_text(user.get("last_gift"))
    if msg:
        return await interaction.response.send_message(embed=embed("Un peu de patience !", msg, GOLD), ephemeral=True)
    amount = random.randint(80, 200)
    user["coins"] += amount
    user["last_gift"] = now.isoformat()
    save_data()
    await interaction.response.send_message(embed=embed("Cadeau ouvert !", f"Tu reçois **{fmt(amount)} flocons** !\n\nTon portefeuille contient maintenant ❄️ **{fmt(user['coins'])} flocons**."))


@bot.tree.command(name="daily", description="Récupère tes flocons quotidiens (bonus de série !)")
async def daily(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Utilise cette commande dans un serveur 🎁", ephemeral=True)
    user = get_user(interaction.user.id)
    msg = cooldown_text(user.get("last_daily"))
    if msg:
        return await interaction.response.send_message(embed=embed("Un peu de patience !", msg, GOLD), ephemeral=True)
    now = datetime.now(timezone.utc)
    last = user.get("last_daily")
    if last and now - datetime.fromisoformat(last) <= timedelta(hours=48):
        user["streak"] += 1
    else:
        user["streak"] = 1
    bonus = min(user["streak"] - 1, 10) * 10
    total = 100 + bonus
    user["coins"] += total
    user["last_daily"] = now.isoformat()
    save_data()
    await interaction.response.send_message(embed=embed(
        "Récompense quotidienne",
        f"Tu gagnes **{total} flocons** !\n🔥 Série : **{user['streak']} jour(s)** (bonus : +{bonus})\nSolde : ❄️ **{fmt(user['coins'])} flocons**.",
    ))


@bot.tree.command(name="solde", description="Consulte ton portefeuille de flocons")
@app_commands.describe(membre="Membre à consulter (facultatif)")
async def solde(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    user = get_user(target.id)
    inventory = [f"{SHOP[k]['emoji']} {SHOP[k]['name']}" for k in user["inventory"] if k in SHOP]
    desc = (
        f"💰 Solde : ❄️ **{fmt(user['coins'])} flocons**\n"
        f"🔥 Série quotidienne : **{user['streak']}** jour(s)\n"
        f"🎒 Objets : {', '.join(inventory) if inventory else 'aucun pour le moment'}"
    )
    await interaction.response.send_message(embed=embed(f"Le sac de {esc(target.display_name)}", desc))


@bot.tree.command(name="boutique", description="Découvre la boutique de Noël")
async def boutique(interaction: discord.Interaction):
    lines = [f"{item['emoji']} **{item['name']}** — {item['price']} flocons\n`/acheter objet:{key}`" for key, item in SHOP.items()]
    await interaction.response.send_message(embed=embed("La boutique du Pôle Nord", "\n\n".join(lines)))


@bot.tree.command(name="acheter", description="Achète un objet dans la boutique")
@app_commands.choices(objet=SHOP_CHOICES)
async def acheter(interaction: discord.Interaction, objet: app_commands.Choice[str]):
    if not interaction.guild:
        return await interaction.response.send_message("Utilise cette commande dans un serveur.", ephemeral=True)
    item = SHOP[objet.value]
    user = get_user(interaction.user.id)
    if objet.value in user["inventory"]:
        return await interaction.response.send_message("Tu possèdes déjà cet objet ! 🎒", ephemeral=True)
    if user["coins"] < item["price"]:
        return await interaction.response.send_message(embed=embed("Pas assez de flocons", f"Il te manque **{item['price'] - user['coins']} flocons**. Tente `/daily` demain !", RED), ephemeral=True)
    user["coins"] -= item["price"]
    user["inventory"].append(objet.value)
    save_data()
    await interaction.response.send_message(embed=embed("Achat réussi !", f"{item['emoji']} Tu as obtenu **{item['name']}**.\nIl te reste ❄️ **{fmt(user['coins'])} flocons**."))


@bot.tree.command(name="donner", description="Offre des flocons à un autre membre")
@app_commands.describe(membre="Le destinataire", montant="Nombre de flocons à offrir")
async def donner(interaction: discord.Interaction, membre: discord.Member, montant: app_commands.Range[int, 1, 100000]):
    if membre.bot or membre.id == interaction.user.id:
        return await interaction.response.send_message("Choisis quelqu'un d'autre pour ton cadeau 🎁", ephemeral=True)
    giver = get_user(interaction.user.id)
    if giver["coins"] < montant:
        return await interaction.response.send_message(embed=embed("Pas assez de flocons", f"Il te manque **{fmt(montant - giver['coins'])} flocons**.", RED), ephemeral=True)
    receiver = get_user(membre.id)
    giver["coins"] -= montant
    receiver["coins"] += montant
    save_data()
    await interaction.response.send_message(embed=embed("Quelle générosité !", f"{interaction.user.mention} offre **{fmt(montant)} flocons** à {membre.mention} 🎁"))


@bot.tree.command(name="classement", description="Les plus riches en flocons du serveur")
async def classement(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Utilise cette commande dans un serveur.", ephemeral=True)
    ranking = []
    for uid, u in data["users"].items():
        member = interaction.guild.get_member(int(uid))
        if member and not member.bot and u.get("coins", 0) > 0:
            ranking.append((member, u["coins"]))
    ranking.sort(key=lambda x: x[1], reverse=True)
    if not ranking:
        return await interaction.response.send_message(embed=embed("Classement", "Personne n'a encore de flocons. Lance `/daily` !"))
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{medals[i] if i < 3 else f'**{i + 1}.**'} {esc(m.display_name)} — ❄️ {fmt(c)}" for i, (m, c) in enumerate(ranking[:10])]
    await interaction.response.send_message(embed=embed("Les plus riches du Pôle Nord", "\n".join(lines)))


@bot.tree.command(name="pari", description="Pile ou face avec tes flocons : double ou rien !")
@app_commands.describe(montant="Mise (10 à 1 000 flocons)", choix="Pile ou face ?")
@app_commands.choices(choix=[
    app_commands.Choice(name="Pile", value="pile"),
    app_commands.Choice(name="Face", value="face"),
])
@app_commands.checks.cooldown(1, 10.0, key=lambda i: (i.guild_id, i.user.id))
async def pari(interaction: discord.Interaction, montant: app_commands.Range[int, 10, 1000], choix: app_commands.Choice[str]):
    user = get_user(interaction.user.id)
    if user["coins"] < montant:
        return await interaction.response.send_message(embed=embed("Pas assez de flocons", f"Il te manque **{fmt(montant - user['coins'])} flocons**.", RED), ephemeral=True)
    result = random.choice(["pile", "face"])
    if result == choix.value:
        user["coins"] += montant
        title, text, color = "Gagné !", f"La pièce tombe sur **{result}** ! Tu gagnes **{fmt(montant)} flocons** 🎉", GREEN
    else:
        user["coins"] -= montant
        title, text, color = "Perdu…", f"La pièce tombe sur **{result}**. Tu perds **{fmt(montant)} flocons** 🥶", RED
    save_data()
    await interaction.response.send_message(embed=embed(title, f"{text}\nSolde : ❄️ **{fmt(user['coins'])} flocons**", color))


# ───────────────────────── Noël & calendrier de l'Avent ─────────────────────────

@bot.tree.command(name="noel", description="Compte à rebours jusqu'à Noël")
async def noel(interaction: discord.Interaction):
    now, xmas = next_christmas()
    if now.month == 12 and now.day == 25:
        return await interaction.response.send_message(embed=embed("Joyeux Noël !", "C'est aujourd'hui ! 🎅🎁✨ Profite bien avec tes proches !", GOLD))
    days = (xmas.date() - now.date()).days
    await interaction.response.send_message(embed=embed(
        "Compte à rebours",
        f"Noël arrive <t:{int(xmas.timestamp())}:R> !\n🗓️ Plus que **{days} jour(s)** avant le 25 décembre 🎄",
    ))


@bot.tree.command(name="avent", description="Ouvre la case du jour du calendrier de l'Avent (1er–24 décembre)")
async def avent(interaction: discord.Interaction):
    now = datetime.now(TZ)
    if now.month != 12 or now.day > 24:
        year = now.year if now.month < 12 else now.year + 1
        start = datetime(year, 12, 1, tzinfo=TZ)
        return await interaction.response.send_message(embed=embed("Calendrier fermé", f"Les cases ouvrent le 1er décembre : <t:{int(start.timestamp())}:R> 🎄", GOLD), ephemeral=True)
    user = get_user(interaction.user.id)
    key = f"{now.year}-{now.day}"
    if key in user["advent"]:
        return await interaction.response.send_message(embed=embed("Déjà ouverte !", f"Tu as déjà ouvert la case **{now.day}**. Reviens demain ! 🎁", GOLD), ephemeral=True)
    reward = 500 if now.day == 24 else random.randint(50, 150)
    user["advent"].append(key)
    user["coins"] += reward
    save_data()
    opened = sum(1 for k in user["advent"] if k.startswith(f"{now.year}-"))
    await interaction.response.send_message(embed=embed(
        f"Case n°{now.day} ouverte !",
        f"Tu trouves **{fmt(reward)} flocons** 🎁\nCases ouvertes : **{opened}/24**\nSolde : ❄️ **{fmt(user['coins'])} flocons**",
    ))


@bot.tree.command(name="blague", description="Une blague de Noël")
async def blague(interaction: discord.Interaction):
    await interaction.response.send_message(embed=embed("La blague du lutin", random.choice(JOKES)))


@bot.tree.command(name="idee-cadeau", description="Une idée de cadeau au hasard")
async def idee_cadeau(interaction: discord.Interaction):
    await interaction.response.send_message(embed=embed("Idée de cadeau", random.choice(GIFT_IDEAS)))


@bot.tree.command(name="boule-de-neige", description="Lance une boule de neige sur un membre")
@app_commands.describe(membre="La cible")
@app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
async def boule_de_neige(interaction: discord.Interaction, membre: discord.Member):
    if membre.bot or membre.id == interaction.user.id:
        return await interaction.response.send_message("Choisis une autre cible ! ⛄", ephemeral=True)
    roll = random.random()
    user = get_user(interaction.user.id)
    if roll < 0.15:
        user["coins"] += 25
        text = f"💥 **Coup critique !** {interaction.user.mention} envoie une boule de neige en pleine tête de {membre.mention} ! (+25 flocons)"
    elif roll < 0.65:
        user["coins"] += 10
        text = f"❄️ {interaction.user.mention} touche {membre.mention} en plein dans le bonnet ! (+10 flocons)"
    else:
        text = f"🌨️ {membre.mention} esquive avec style la boule de {interaction.user.mention}… dans le décor !"
    save_data()
    await interaction.response.send_message(embed=embed("Bataille de boules de neige", text))


# ───────────────────────── Quiz ─────────────────────────

class QuizView(discord.ui.View):
    def __init__(self, user, options, correct_index):
        super().__init__(timeout=25)
        self.user = user
        self.correct_index = correct_index
        self.answered = False
        self.message = None
        for i, text in enumerate(options):
            btn = discord.ui.Button(label=text[:80], style=discord.ButtonStyle.secondary)
            btn.callback = self.make_callback(i)
            self.add_item(btn)

    def make_callback(self, index):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("Ce n'est pas ton quiz ! 🎅", ephemeral=True)
            self.answered = True
            for i, child in enumerate(self.children):
                child.disabled = True
                if i == self.correct_index:
                    child.style = discord.ButtonStyle.success
                elif i == index:
                    child.style = discord.ButtonStyle.danger
            if index == self.correct_index:
                u = get_user(self.user.id)
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if u["quiz_day"] != today:
                    u["quiz_day"], u["quiz_count"] = today, 0
                if u["quiz_count"] < 3:
                    u["quiz_count"] += 1
                    u["coins"] += 30
                    save_data()
                    text = f"Bravo ! **+30 flocons** 🎉 ({u['quiz_count']}/3 récompenses aujourd'hui)"
                else:
                    text = "Bravo ! 🎉 (limite de 3 récompenses par jour atteinte)"
                result = embed("Bonne réponse !", text)
            else:
                result = embed("Raté !", "Ce n'est pas la bonne réponse… Retente ta chance ! 🥶", RED)
            await interaction.response.edit_message(embed=result, view=self)
            self.stop()
        return callback

    async def on_timeout(self):
        if self.answered or not self.message:
            return
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(embed=embed("Temps écoulé", "Les lutins ont rangé le quiz ⏰", GOLD), view=self)
        except discord.HTTPException:
            pass


@bot.tree.command(name="quiz", description="Un quiz de Noël : gagne 30 flocons (3 fois par jour)")
@app_commands.checks.cooldown(1, 20.0, key=lambda i: (i.guild_id, i.user.id))
async def quiz(interaction: discord.Interaction):
    question, good, bad = random.choice(QUIZ)
    options = [good] + bad
    random.shuffle(options)
    view = QuizView(interaction.user, options, options.index(good))
    await interaction.response.send_message(embed=embed("Quiz de Noël", f"**{question}**\nTu as 25 secondes ⏳"), view=view)
    view.message = await interaction.original_response()


# ───────────────────────── Secret Santa ─────────────────────────

class SantaView(discord.ui.View):
    def __init__(self, creator, event_title, budget):
        super().__init__(timeout=7200)
        self.creator = creator
        self.event_title = event_title
        self.budget = budget
        self.participants = {}
        self.draws = 0

    def build_embed(self):
        names = "\n".join(f"🎁 {m.mention}" for m in self.participants.values()) or "*Personne pour le moment*"
        desc = (
            f"**{esc(self.event_title)}**\n💶 Budget : {esc(self.budget)}\n\n"
            f"Participants ({len(self.participants)}) :\n{names}\n\n"
            f"{self.creator.mention} lancera le tirage (3 participants minimum)."
        )
        return embed("Secret Santa 🎅", desc)

    @discord.ui.button(label="Je participe", emoji="🎅", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.participants[interaction.user.id] = interaction.user
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Me retirer", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.participants.pop(interaction.user.id, None)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Lancer le tirage", emoji="🎲", style=discord.ButtonStyle.primary)
    async def draw(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator.id:
            return await interaction.response.send_message("Seul l'organisateur peut lancer le tirage.", ephemeral=True)
        if len(self.participants) < 3:
            return await interaction.response.send_message("Il faut au moins 3 participants.", ephemeral=True)
        await interaction.response.defer()
        members = list(self.participants.values())
        random.shuffle(members)
        self.draws += 1
        failed = []
        for i, giver in enumerate(members):
            receiver = members[(i + 1) % len(members)]
            try:
                await giver.send(embed=embed(
                    f"Secret Santa — tirage n°{self.draws}",
                    f"Tu dois offrir un cadeau à **{esc(receiver.display_name)}** 🎁\n"
                    f"Événement : {esc(self.event_title)}\nBudget : {esc(self.budget)}\n\n"
                    "Chut, c'est un secret ! 🤫 (Ce tirage remplace les éventuels précédents.)",
                ))
            except discord.HTTPException:
                failed.append(giver)
        if failed:
            mentions = ", ".join(m.mention for m in failed)
            return await interaction.followup.send(
                f"Je n'ai pas pu envoyer de MP à : {mentions}. Demande-leur d'ouvrir leurs messages privés puis relance le tirage (il remplacera le précédent).",
                ephemeral=True,
            )
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(
            embed=embed("Tirage effectué !", f"Les **{len(members)} participants** ont reçu leur cible par message privé 🤫🎅"),
            view=self,
        )
        self.stop()


@bot.tree.command(name="secret-santa", description="Organise un Secret Santa")
@app_commands.describe(titre="Nom de l'événement", budget="Budget conseillé (ex. 15 €)")
async def secret_santa(interaction: discord.Interaction, titre: str = "Secret Santa du serveur", budget: str = "15 €"):
    if not interaction.guild:
        return await interaction.response.send_message("Utilise cette commande dans un serveur.", ephemeral=True)
    view = SantaView(interaction.user, titre[:80], budget[:30])
    await interaction.response.send_message(embed=view.build_embed(), view=view)


# ───────────────────────── Liste de souhaits ─────────────────────────

souhait = app_commands.Group(name="souhait", description="Ta liste de cadeaux de Noël")


@souhait.command(name="ajouter", description="Ajoute un cadeau à ta liste")
@app_commands.describe(cadeau="Le cadeau souhaité")
async def souhait_ajouter(interaction: discord.Interaction, cadeau: app_commands.Range[str, 1, 100]):
    user = get_user(interaction.user.id)
    if len(user["wishlist"]) >= 10:
        return await interaction.response.send_message("Ta liste est pleine (10 max). Retire un cadeau avec `/souhait retirer`.", ephemeral=True)
    user["wishlist"].append(cadeau)
    save_data()
    await interaction.response.send_message(embed=embed("Ajouté à ta liste !", f"🎁 {esc(cadeau)}\n({len(user['wishlist'])}/10)"), ephemeral=True)


@souhait.command(name="retirer", description="Retire un cadeau de ta liste")
@app_commands.describe(numero="Numéro du cadeau (voir /souhait voir)")
async def souhait_retirer(interaction: discord.Interaction, numero: app_commands.Range[int, 1, 10]):
    user = get_user(interaction.user.id)
    if numero > len(user["wishlist"]):
        return await interaction.response.send_message("Ce numéro n'existe pas dans ta liste.", ephemeral=True)
    removed = user["wishlist"].pop(numero - 1)
    save_data()
    await interaction.response.send_message(embed=embed("Retiré", f"🗑️ {esc(removed)}"), ephemeral=True)


@souhait.command(name="voir", description="Affiche ta liste ou celle d'un membre")
@app_commands.describe(membre="Membre à consulter (facultatif)")
async def souhait_voir(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    wishes = get_user(target.id)["wishlist"]
    desc = "\n".join(f"**{i}.** {esc(w)}" for i, w in enumerate(wishes, start=1)) or "Aucun souhait pour le moment."
    await interaction.response.send_message(embed=embed(f"Liste de {esc(target.display_name)}", desc))


bot.tree.add_command(souhait)


# ───────────────────────── Événements ─────────────────────────

@bot.tree.command(name="event-creer", description="Crée un événement de Noël")
@app_commands.default_permissions(manage_events=True)
@app_commands.describe(nom="Nom de l'événement", date="Date au format AAAA-MM-JJ HH:MM (heure de Paris)", description="Description facultative")
async def event_creer(interaction: discord.Interaction, nom: str, date: str, description: str = "Un moment magique au Pôle Nord !"):
    if not interaction.guild:
        return await interaction.response.send_message("Cette commande doit être utilisée dans un serveur.", ephemeral=True)
    try:
        when = parse_date(date)
    except ValueError:
        return await interaction.response.send_message("Format de date incorrect. Exemple : `2026-12-24 20:00`.", ephemeral=True)
    if when <= datetime.now(timezone.utc):
        return await interaction.response.send_message("Choisis une date dans le futur !", ephemeral=True)
    event_id = str(int(datetime.now().timestamp() * 1000))
    data["events"][event_id] = {
        "guild_id": interaction.guild_id, "channel_id": interaction.channel_id,
        "name": nom[:80], "description": description[:300],
        "date": when.isoformat(), "creator": interaction.user.id, "notified": False,
    }
    save_data()
    unix = int(when.timestamp())
    await interaction.response.send_message(embed=embed("Événement ajouté !", f"**{esc(nom)}**\n{esc(description)}\n🗓️ <t:{unix}:F>\n\nUn rappel sera envoyé ici 15 minutes avant. Retrouve-le avec `/events` !"))


@bot.tree.command(name="events", description="Affiche les prochains événements de Noël")
async def events(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Cette commande doit être utilisée dans un serveur.", ephemeral=True)
    now = datetime.now(timezone.utc).timestamp()
    upcoming = [
        e for e in data["events"].values()
        if e["guild_id"] == interaction.guild_id and datetime.fromisoformat(e["date"]).timestamp() > now
    ]
    upcoming.sort(key=lambda e: e["date"])
    if not upcoming:
        desc = "Aucun événement prévu pour le moment. Les lutins attendent une idée !"
    else:
        desc = "\n\n".join(f"🎄 **{esc(e['name'])}**\n<t:{int(datetime.fromisoformat(e['date']).timestamp())}:F>\n{esc(e['description'])}" for e in upcoming[:10])
    await interaction.response.send_message(embed=embed("Calendrier des festivités", desc))


# ───────────────────────── Vocal & musique ─────────────────────────

async def ensure_voice(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("Utilise cette commande dans un serveur.", ephemeral=True)
        return None
    voice_channel = interaction.user.voice.channel if interaction.user.voice else None
    if voice_channel is None:
        await interaction.response.send_message("Rejoins d'abord un salon vocal ! 🎶", ephemeral=True)
        return None
    if not interaction.guild.voice_client:
        try:
            voice = await voice_channel.connect()
        except Exception as exc:
            await interaction.response.send_message(f"Je n'arrive pas à rejoindre le vocal : {exc}", ephemeral=True)
            return None
    else:
        voice = interaction.guild.voice_client
        if voice.channel != voice_channel:
            await voice.move_to(voice_channel)
    queue = music_queues.get(interaction.guild_id)
    if queue is None:
        queue = {"songs": [], "current": None, "voice": voice, "text_channel": interaction.channel,
                 "volume": 0.35, "loop": False, "source": None}
        music_queues[interaction.guild_id] = queue
    else:
        queue["voice"] = voice
        queue["text_channel"] = interaction.channel
    return queue


async def active_queue(interaction: discord.Interaction):
    """File existante pour les commandes de contrôle (pause, volume…)."""
    queue = music_queues.get(interaction.guild_id)
    if not queue:
        await interaction.response.send_message("Aucune musique en cours. Utilise `/play` !", ephemeral=True)
        return None
    return queue


@bot.tree.command(name="rejoindre", description="Fais rejoindre Frosty à ton salon vocal")
async def rejoindre(interaction: discord.Interaction):
    queue = await ensure_voice(interaction)
    if queue is None:
        return
    await interaction.response.send_message(embed=embed("Frosty a rejoint le vocal !", f"Salon : **{esc(queue['voice'].channel.name)}**\nLance une piste avec `/play`."))


@bot.tree.command(name="play", description="Joue une piste depuis une URL prise en charge")
@app_commands.describe(url="URL d'une vidéo ou piste audio")
async def play_cmd(interaction: discord.Interaction, url: str):
    if yt_dlp is None:
        return await interaction.response.send_message("La musique nécessite `yt-dlp`. Installe-le avec `pip install yt-dlp`.", ephemeral=True)
    queue = await ensure_voice(interaction)
    if queue is None:
        return
    await interaction.response.defer()
    try:
        song = await get_music_info(url)
    except Exception as exc:
        return await interaction.followup.send(f"Je n'arrive pas à lire cette URL. Vérifie le lien et réessaie. (`{str(exc)[:150]}`)")
    song["requester"] = interaction.user.display_name
    queue["songs"].append(song)
    if not queue["voice"].is_playing() and not queue["voice"].is_paused() and queue["current"] is None:
        await play_next(interaction.guild_id)
    await interaction.followup.send(embed=embed("Piste ajoutée à la hotte 🎁", f"🎶 **{esc(song['title'])}**\nPistes en attente : **{len(queue['songs'])}**"))


@bot.tree.command(name="queue", description="Affiche la file musicale")
async def queue_cmd(interaction: discord.Interaction):
    queue = music_queues.get(interaction.guild_id)
    if not queue:
        return await interaction.response.send_message("La file musicale est vide. Utilise `/rejoindre` puis `/play`.", ephemeral=True)
    lines = [f"▶️ **En cours :** {esc(queue['current']['title'])}" if queue.get("current") else "⏸️ Aucune piste en cours"]
    lines += [f"{i}. {esc(s['title'])} — {esc(s['requester'])}" for i, s in enumerate(queue["songs"][:10], start=1)]
    if queue.get("loop"):
        lines.append("\n🔁 Boucle activée")
    await interaction.response.send_message(embed=embed("File musicale", "\n".join(lines)))


@bot.tree.command(name="nowplaying", description="Affiche la piste en cours")
async def nowplaying(interaction: discord.Interaction):
    queue = music_queues.get(interaction.guild_id)
    if not queue or not queue.get("current"):
        return await interaction.response.send_message("Aucune piste n'est en cours.", ephemeral=True)
    song = queue["current"]
    await interaction.response.send_message(embed=embed("À l'écoute 🎶", f"[{esc(song['title'])}]({song['url']})\nAjouté par {esc(song['requester'])}\n🔊 Volume : {int(queue['volume'] * 100)} %"))


@bot.tree.command(name="pause", description="Met la musique en pause")
async def pause(interaction: discord.Interaction):
    queue = await active_queue(interaction)
    if queue is None:
        return
    if not queue["voice"].is_playing():
        return await interaction.response.send_message("Rien à mettre en pause.", ephemeral=True)
    queue["voice"].pause()
    await interaction.response.send_message(embed=embed("Pause ⏸️", "Reprends avec `/resume`."))


@bot.tree.command(name="resume", description="Reprend la musique")
async def resume(interaction: discord.Interaction):
    queue = await active_queue(interaction)
    if queue is None:
        return
    if not queue["voice"].is_paused():
        return await interaction.response.send_message("La musique n'est pas en pause.", ephemeral=True)
    queue["voice"].resume()
    await interaction.response.send_message(embed=embed("C'est reparti ▶️", "On reprend la musique !"))


@bot.tree.command(name="volume", description="Règle le volume (1 à 100)")
@app_commands.describe(niveau="Volume en pourcentage")
async def volume(interaction: discord.Interaction, niveau: app_commands.Range[int, 1, 100]):
    queue = await active_queue(interaction)
    if queue is None:
        return
    queue["volume"] = niveau / 100
    if queue.get("source"):
        queue["source"].volume = niveau / 100
    await interaction.response.send_message(embed=embed("Volume réglé 🔊", f"Volume à **{niveau} %**."))


@bot.tree.command(name="melanger", description="Mélange la file d'attente")
async def melanger(interaction: discord.Interaction):
    queue = await active_queue(interaction)
    if queue is None:
        return
    if len(queue["songs"]) < 2:
        return await interaction.response.send_message("Il faut au moins 2 pistes en attente.", ephemeral=True)
    random.shuffle(queue["songs"])
    await interaction.response.send_message(embed=embed("File mélangée 🔀", "Les lutins ont tout rebattu !"))


@bot.tree.command(name="boucle", description="Active ou désactive la boucle de la file")
async def boucle(interaction: discord.Interaction):
    queue = await active_queue(interaction)
    if queue is None:
        return
    queue["loop"] = not queue.get("loop", False)
    await interaction.response.send_message(embed=embed("Boucle 🔁", "Boucle **activée**." if queue["loop"] else "Boucle **désactivée**."))


@bot.tree.command(name="skip", description="Passe à la piste suivante")
async def skip(interaction: discord.Interaction):
    queue = music_queues.get(interaction.guild_id)
    if not queue or not queue.get("current"):
        return await interaction.response.send_message("Aucune piste n'est en cours.", ephemeral=True)
    queue["current"] = None
    queue["voice"].stop()
    await interaction.response.send_message(embed=embed("Piste passée ⏭️", "On enchaîne avec la suite !"))


@bot.tree.command(name="stop", description="Arrête la musique et vide la file")
async def stop(interaction: discord.Interaction):
    queue = music_queues.pop(interaction.guild_id, None)
    if not queue:
        return await interaction.response.send_message("La musique est déjà arrêtée.", ephemeral=True)
    queue["songs"].clear()
    queue["current"] = None
    if queue["voice"].is_playing() or queue["voice"].is_paused():
        queue["voice"].stop()
    await queue["voice"].disconnect(force=True)
    await interaction.response.send_message(embed=embed("Silence au Pôle Nord", "La musique est arrêtée et la file a été vidée."))


# ───────────────────────── Aide ─────────────────────────

@bot.tree.command(name="aide", description="Liste des commandes de Frosty")
async def aide(interaction: discord.Interaction):
    desc = (
        "**💰 Économie** : `/daily` `/cadeau` `/solde` `/boutique` `/acheter` `/donner` `/classement` `/pari`\n\n"
        "**🎄 Noël** : `/noel` `/avent` `/blague` `/idee-cadeau` `/boule-de-neige` `/quiz`\n\n"
        "**🎅 Entre amis** : `/secret-santa` `/souhait ajouter|retirer|voir`\n\n"
        "**🗓️ Événements** : `/event-creer` `/events`\n\n"
        "**🎶 Musique** : `/rejoindre` `/play` `/pause` `/resume` `/skip` `/stop` `/queue` `/nowplaying` `/volume` `/melanger` `/boucle`"
    )
    await interaction.response.send_message(embed=embed("Les commandes de Frosty", desc))


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Ajoute DISCORD_TOKEN dans un fichier .env à côté de main.py.")
    bot.run(TOKEN)
