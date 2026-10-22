# Frosty 🎄 — Bot Discord de Noël en Python
# Installation :
#   pip install -U discord.py python-dotenv yt-dlp
# Installe aussi FFmpeg et ajoute-le au PATH pour la musique.
# Crée un fichier .env à côté de main.py contenant :
#   DISCORD_TOKEN=TON_TOKEN_DISCORD
#   GUILD_ID=ID_DE_TON_SERVEUR   (facultatif, commandes disponibles plus vite en test)
#
# Dans le portail développeur Discord, active les scopes bot et applications.commands.
# Permissions conseillées : View Channels, Send Messages, Embed Links, Connect, Speak.

import os
import json
import random
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

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
    "traineau": {"name": "Traîneau doré", "price": 750, "emoji": "🛷"},
}

# État musical en mémoire : la file est remise à zéro lorsque le bot redémarre.
music_queues = {}
music_locks = {}


def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"users": {}, "events": {}}


data = load_data()


def save_data():
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_user(user_id: int):
    key = str(user_id)
    if key not in data["users"]:
        data["users"][key] = {
            "coins": 0,
            "last_daily": None,
            "last_gift": None,
            "inventory": [],
        }
    return data["users"][key]


def embed(title: str, description: str, color: int = GREEN):
    e = discord.Embed(title=f"🎄 {title}", description=description, color=color)
    e.set_footer(text="Frosty • L'esprit de Noël toute l'année")
    return e


def parse_date(text: str):
    # Format conseillé : 2026-12-24 20:00. Interprété dans le fuseau local de la machine.
    return datetime.strptime(text, "%Y-%m-%d %H:%M").astimezone()


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
    if not queue or not queue["songs"]:
        if queue:
            queue["current"] = None
        return

    song = queue["songs"].pop(0)
    queue["current"] = song
    try:
        source = discord.FFmpegPCMAudio(
            song["stream_url"],
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn",
        )
        source = discord.PCMVolumeTransformer(source, volume=0.35)

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
            await channel.send(embed=embed("À l'écoute 🎶", f"**{discord.utils.escape_markdown(song['title'])}**\nAjouté par {song['requester']}"))
    except Exception as exc:
        print(f"Impossible de lire la piste : {exc}")
        channel = queue.get("text_channel")
        if channel:
            await channel.send(embed=embed("Petit couac musical", "Impossible de lire cette piste. Je passe à la suivante.", RED))
        await play_next(guild_id)


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
    await interaction.response.send_message(embed=embed("Cadeau ouvert !", f"Tu reçois **{amount:,} flocons** !\n\nTon portefeuille contient maintenant ❄️ **{user['coins']:,} flocons**.".replace(",", " ")))

@bot.tree.command(name="daily", description="Récupère tes 100 flocons quotidiens")
async def daily(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Utilise cette commande dans un serveur 🎁", ephemeral=True)
    user = get_user(interaction.user.id)
    msg = cooldown_text(user.get("last_daily"))
    if msg:
        return await interaction.response.send_message(embed=embed("Un peu de patience !", msg, GOLD), ephemeral=True)
    user["coins"] += 100
    user["last_daily"] = datetime.now(timezone.utc).isoformat()
    save_data()
    await interaction.response.send_message(embed=embed("Récompense quotidienne", f"Tu gagnes **100 flocons** !\nSolde : ❄️ **{user['coins']} flocons**."))


@bot.tree.command(name="solde", description="Consulte ton portefeuille de flocons")
@app_commands.describe(membre="Membre à consulter (facultatif)")
async def solde(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    user = get_user(target.id)
    inventory = [SHOP[k]["name"] for k in user["inventory"] if k in SHOP]
    desc = f"💰 Solde : ❄️ **{user['coins']:,} flocons**\n🎒 Objets : {', '.join(inventory) if inventory else 'aucun pour le moment'}"
    await interaction.response.send_message(embed=embed(f"Le sac de {target.display_name}", desc.replace(",", " ")))


@bot.tree.command(name="boutique", description="Découvre la boutique de Noël")
async def boutique(interaction: discord.Interaction):
    lines = [f"{item['emoji']} **{item['name']}** — {item['price']} flocons\n`/acheter objet:{key}`" for key, item in SHOP.items()]
    await interaction.response.send_message(embed=embed("La boutique du Pôle Nord", "\n\n".join(lines)))


@bot.tree.command(name="acheter", description="Achète un objet dans la boutique")
@app_commands.choices(objet=[
    app_commands.Choice(name="Bonnet d'elfe — 100 flocons", value="bonnet"),
    app_commands.Choice(name="Canne en sucre — 250 flocons", value="canne"),
    app_commands.Choice(name="Traîneau doré — 750 flocons", value="traineau"),
])
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
    await interaction.response.send_message(embed=embed("Achat réussi !", f"{item['emoji']} Tu as obtenu **{item['name']}**.\nIl te reste ❄️ **{user['coins']} flocons**."))


@bot.tree.command(name="event-creer", description="Crée un événement de Noël")
@app_commands.default_permissions(manage_events=True)
@app_commands.describe(nom="Nom de l'événement", date="Date au format AAAA-MM-JJ HH:MM", description="Description facultative")
async def event_creer(interaction: discord.Interaction, nom: str, date: str, description: str = "Un moment magique au Pôle Nord !"):
    if not interaction.guild:
        return await interaction.response.send_message("Cette commande doit être utilisée dans un serveur.", ephemeral=True)
    try:
        when = parse_date(date)
    except ValueError:
        return await interaction.response.send_message("Format de date incorrect. Exemple : `2026-12-24 20:00`.", ephemeral=True)
    if when <= datetime.now().astimezone():
        return await interaction.response.send_message("Choisis une date dans le futur !", ephemeral=True)
    event_id = str(int(datetime.now().timestamp() * 1000))
    data["events"][event_id] = {
        "guild_id": interaction.guild_id, "name": nom[:80], "description": description[:300],
        "date": when.isoformat(), "creator": interaction.user.id
    }
    save_data()
    unix = int(when.timestamp())
    await interaction.response.send_message(embed=embed("Événement ajouté !", f"**{discord.utils.escape_markdown(nom)}**\n{discord.utils.escape_markdown(description)}\n🗓️ <t:{unix}:F>\n\nRetrouve-le avec `/events` !"))


@bot.tree.command(name="events", description="Affiche les prochains événements de Noël")
async def events(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Cette commande doit être utilisée dans un serveur.", ephemeral=True)
    upcoming = [
        e for e in data["events"].values()
        if e["guild_id"] == interaction.guild_id and datetime.fromisoformat(e["date"]).timestamp() > datetime.now().timestamp()
    ]
    upcoming.sort(key=lambda e: e["date"])
    if not upcoming:
        desc = "Aucun événement prévu pour le moment. Les lutins attendent une idée !"
    else:
        desc = "\n\n".join(f"🎄 **{discord.utils.escape_markdown(e['name'])}**\n<t:{int(datetime.fromisoformat(e['date']).timestamp())}:F>\n{discord.utils.escape_markdown(e['description'])}" for e in upcoming[:10])
    await interaction.response.send_message(embed=embed("Calendrier des festivités", desc))


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
        queue = {"songs": [], "current": None, "voice": voice, "text_channel": interaction.channel}
        music_queues[interaction.guild_id] = queue
    else:
        queue["voice"] = voice
        queue["text_channel"] = interaction.channel
    return queue


@bot.tree.command(name="rejoindre", description="Fais rejoindre Frosty à ton salon vocal")
async def rejoindre(interaction: discord.Interaction):
    queue = await ensure_voice(interaction)
    if queue is None:
        return
    await interaction.response.send_message(embed=embed("Frosty a rejoint le vocal !", f"Salon : **{queue['voice'].channel.name}**\nLance une piste avec `/play`."))


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
    await interaction.followup.send(embed=embed("Piste ajoutée à la hotte 🎁", f"🎶 **{discord.utils.escape_markdown(song['title'])}**\nPistes en attente : **{len(queue['songs'])}**"))


@bot.tree.command(name="queue", description="Affiche la file musicale")
async def queue_cmd(interaction: discord.Interaction):
    queue = music_queues.get(interaction.guild_id)
    if not queue:
        return await interaction.response.send_message("La file musicale est vide. Utilise `/rejoindre` puis `/play`.", ephemeral=True)
    lines = [f"▶️ **En cours :** {queue['current']['title']}" if queue.get("current") else "⏸️ Aucune piste en cours"]
    lines += [f"{i}. {s['title']} — {s['requester']}" for i, s in enumerate(queue["songs"][:10], start=1)]
    await interaction.response.send_message(embed=embed("File musicale", "\n".join(lines)))


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


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Ajoute DISCORD_TOKEN dans un fichier .env à côté de main.py.")
    bot.run(TOKEN)
