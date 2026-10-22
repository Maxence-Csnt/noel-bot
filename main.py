import os
import random
import discord
from discord import app_commands

# Utilisation des intents par défaut (sans privilèges restreints)
intents = discord.Intents.default()

class HalloweenBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("🎃 Commandes d'Halloween synchronisées avec succès ! 👻")

client = HalloweenBot()

# Dictionnaire pour stocker les bonbons des utilisateurs
chaudrons = {}

@client.event
async def on_ready():
    print(f"👻 Bot Halloween connecté en tant que {client.user} ! 🦇")
    await client.change_presence(activity=discord.Game(name="Événement d'Halloween 🎃 | /halloween"))

# --- COMMANDES SLASH ---

@client.tree.command(name="halloween", description="Détails et explications de l'évènement d'Halloween 🎃")
async def halloween_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎃 Évènement Saisonnier d'Halloween",
        description="Bienvenue dans l'événement officiel ! Chassez des bonbons, consultez votre chaudron et jetez des sorts ! 🦇🕸️",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="bonbon", description="Offrez des bonbons à la personne de votre choix 🍬")
@app_commands.describe(membre="La personne à qui offrir", nombre="Nombre de bonbons")
async def bonbon(interaction: discord.Interaction, membre: discord.Member, nombre: int):
    if membre == interaction.user:
        await interaction.response.send_message("❌ Tu ne peux pas t'offrir des bonbons à toi-même ! 🎃", ephemeral=True)
        return
    if nombre <= 0:
        await interaction.response.send_message("❌ Il faut offrir au moins 1 bonbon ! 🦇", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🍬 Distribution de bonbons",
        description=f"{interaction.user.mention} offre **{nombre}** délicieux bonbons à {membre.mention} ! 🍫",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="chaudron", description="Jetez un œil à votre chaudron de bonbons magique 🧙‍♀️")
async def chaudron(interaction: discord.Interaction):
    nb_bonbons = chaudrons.get(interaction.user.id, 0)
    embed = discord.Embed(
        title="🧙‍♀️ Le Chaudron Magique",
        description=f"En regardant dans les vapeurs de ton chaudron, tu aperçois **{nb_bonbons} bonbons** qui frémissent ! 🍬🔥",
        color=discord.Color.purple()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="chasse", description="Partez à la chasse aux bonbons dans les bois hantés 🐺")
@app_commands.describe(partenaire="Votre partenaire de chasse")
async def chasse(interaction: discord.Interaction, partenaire: discord.Member):
    if partenaire == interaction.user:
        await interaction.response.send_message("❌ On ne peut pas chasser tout seul dans les bois sombres... Prends un ami ! 🌲", ephemeral=True)
        return
    
    butin = random.randint(1, 5)
    chaudrons[interaction.user.id] = chaudrons.get(interaction.user.id, 0) + butin
    chaudrons[partenaire.id] = chaudrons.get(partenaire.id, 0) + butin

    embed = discord.Embed(
        title="🐺 Chasse aux monstres",
        description=f"{interaction.user.mention} et {partenaire.mention} partent explorer les bois...\n\n🏆 Ils récupèrent chacun **{butin} bonbons** pour leur chaudron ! 🍬",
        color=discord.Color.dark_orange()
    )
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="bouh", description="Faites apparaître une image animée pour effrayer vos amis 🎃")
async def bouh(interaction: discord.Interaction):
    gifs = [
        "https://media.giphy.com/media/3oKIPEhWQVfrAFUDLy/giphy.gif",
        "https://media.giphy.com/media/10osILvZ4ez7ws/giphy.gif",
        "https://media.giphy.com/media/8qXJTU5oEhQZO/giphy.gif"
    ]
    embed = discord.Embed(title="👻 BOUH !", description=f"{interaction.user.mention} essaie de vous faire peur ! 🦇", color=discord.Color.dark_purple())
    embed.set_image(url=random.choice(gifs))
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="grimoire", description="Consultez votre grimoire des créatures d'Halloween 📖")
async def grimoire(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Grimoire des Créatures",
        description="• **Fantôme farceur** (Rare) 👻\n• **Vampire assoiffé** (Épique) 🧛‍♂️\n• **Citrouille maudite** (Légendaire) 🎃\n• **Zombie affamé** (Commun) 🧟‍♂️",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="rituel", description="Faites un rituel pour invoquer des créatures 👻")
async def rituel(interaction: discord.Interaction):
    creatures = ["un Spectre hurlant 👻", "un Loup-garou des ténébres 🐺", "un Squelette danseur 💀"]
    embed = discord.Embed(
        title="🕯️ Cercle d'Invocation",
        description=f"✨ **INVOCATION RÉUSSIE :** {random.choice(creatures)} apparaît dans un nuage de fumée violette ! 🔮",
        color=discord.Color.dark_red()
    )
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="sort", description="Lancez un sort maléfique à un membre du serveur ! 🕷️")
@app_commands.describe(membre="La victime du sortilège")
async def sort(interaction: discord.Interaction, membre: discord.Member):
    sorts = ["transformé en crapaud visqueux 🐸", "maudit avec des chauves-souris dans les cheveux 🦇", "bloqué dans une toile d'araignée 🕸️"]
    embed = discord.Embed(
        title="⚡ Sortilège Noir",
        description=f"{interaction.user.mention} lance un sort sur {membre.mention} !\n\n🔮 Résultat : La cible se retrouve **{random.choice(sorts)}** !",
        color=discord.Color.dark_purple()
    )
    await interaction.response.send_message(embed=embed)

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    client.run(TOKEN)
else:
    print("❌ Erreur : DISCORD_TOKEN introuvable !")
