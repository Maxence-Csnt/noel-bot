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
