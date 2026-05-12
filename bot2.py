import discord
from discord.ext import commands
import json
import os
from datetime import datetime

# Konfiguracja
TOKEN = os.getenv("DISCORD_TOKEN")  # Wklej token swojego bota
GUILD_ID = 1503734776878862386  # Zmień na ID serwera
CHANNEL_ID = 1503754202021626077  # Zmień na ID kanału "na-służbie"

# Rangi i ich priorytety (niższy numer = wyższy priorytet w wyświetlaniu)
RANKS = {
    "Ochroniarz Vipów": 1,
    "ochroniarz stp.3": 2,
    "ochroniarz stp.2": 3,
    "ochroniarz stp.1": 4,
    "Rekrut": 5
}

# Plik do przechowywania danych - kto aktualnie jest na służbie
ON_DUTY_FILE = "na_sluzbie.json"

# Funkcje pomocnicze
def load_on_duty():
    """Ładuje listę ludzi na służbie"""
    if os.path.exists(ON_DUTY_FILE):
        with open(ON_DUTY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_on_duty(user_ids):
    """Zapisuje listę ludzi na służbie"""
    with open(ON_DUTY_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_ids, f, ensure_ascii=False, indent=2)

def get_user_best_role(member):
    """Zwraca najwyższą rangę użytkownika na podstawie ról Discord"""
    best_rank = None
    best_priority = 999
    
    for role in member.roles:
        if role.name in RANKS:
            priority = RANKS[role.name]
            if priority < best_priority:
                best_priority = priority
                best_rank = role.name
    
    return best_rank

def user_has_any_role(member):
    """Sprawdza czy użytkownik ma jakąś rolę ze słuzby"""
    for role in member.roles:
        if role.name in RANKS:
            return True
    return False

def is_on_duty(user_id):
    """Sprawdza czy użytkownik jest na służbie"""
    on_duty_list = load_on_duty()
    return user_id in on_duty_list

def add_to_duty(user_id):
    """Dodaje użytkownika na służbę"""
    on_duty_list = load_on_duty()
    if user_id not in on_duty_list:
        on_duty_list.append(user_id)
        save_on_duty(on_duty_list)
    return True

def remove_from_duty(user_id):
    """Usuwa użytkownika ze służby"""
    on_duty_list = load_on_duty()
    if user_id in on_duty_list:
        on_duty_list.remove(user_id)
        save_on_duty(on_duty_list)
    return True

def get_users_by_rank(guild, rank):
    """Zwraca listę membersów z daną rangą (najwyższą w tej kategorii) i na służbie"""
    users = []
    on_duty_list = load_on_duty()
    
    for member in guild.members:
        if member.bot or member.id not in on_duty_list:
            continue
        
        best_rank = get_user_best_role(member)
        if best_rank == rank:
            users.append(member)
    
    return users

async def create_status_embeds(guild):
    """Tworzy 2 embedy - jeden na służbie, jeden poza - na podstawie ról Discord"""
    
    # EMBED 1: NA SŁUŻBIE - z 5 kategoriami
    embed_on_duty = discord.Embed(
        title="🟢 Na Służbie",
        description=f"Zaktualizowane: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        color=discord.Color.green()
    )
    
    on_duty_empty = True
    for rank in sorted(RANKS.keys(), key=lambda r: RANKS[r]):
        users_with_rank = get_users_by_rank(guild, rank)
        
        if users_with_rank:
            on_duty_empty = False
            user_mentions = [user.mention for user in users_with_rank]
            embed_on_duty.add_field(
                name=rank,
                value="\n".join(user_mentions),
                inline=False
            )
    
    if on_duty_empty:
        embed_on_duty.add_field(
            name="Brak na służbie",
            value="Nikt nie jest teraz na służbie",
            inline=False
        )
    
    # EMBED 2: POZA SŁUŻBĄ
    embed_off_duty = discord.Embed(
        title="🔴 Poza Służbą",
        description=f"Zaktualizowane: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        color=discord.Color.red()
    )
    
    # Zbierz ludzi bez żadnej roli ze służby lub poza listą
    on_duty_list = load_on_duty()
    off_duty = []
    
    for member in guild.members:
        if member.bot:
            continue
        # Jeśli ma rolę ale nie na liście, lub nie ma roli
        if not user_has_any_role(member) or member.id not in on_duty_list:
            off_duty.append(member)
    
    if off_duty:
        off_duty_text = "\n".join([m.mention for m in sorted(off_duty, key=lambda m: m.name)])
        
        if len(off_duty_text) > 1024:
            # Jeśli tekst je za długi, podziel na części
            lines = off_duty_text.split('\n')
            current_field = ""
            field_num = 1
            
            for line in lines:
                if len(current_field) + len(line) + 1 > 1024:
                    embed_off_duty.add_field(
                        name=f"Poza służbą ({field_num})",
                        value=current_field.strip(),
                        inline=False
                    )
                    current_field = line + "\n"
                    field_num += 1
                else:
                    current_field += line + "\n"
            
            if current_field.strip():
                embed_off_duty.add_field(
                    name=f"Poza służbą ({field_num})",
                    value=current_field.strip(),
                    inline=False
                )
        else:
            embed_off_duty.add_field(
                name="Poza służbą",
                value=off_duty_text,
                inline=False
            )
    else:
        embed_off_duty.add_field(
            name="Poza służbą",
            value="Wszyscy są na służbie!",
            inline=False
        )
    
    return embed_on_duty, embed_off_duty

async def update_status_messages(guild, channel):
    """Aktualizuje wiadomości statusu na kanale (2 embedy)"""
    try:
        embed_on_duty, embed_off_duty = await create_status_embeds(guild)
        
        # Szukaj ostatnich dwóch wiadomości bota z embědami
        messages = []
        async for msg in channel.history(limit=10):
            if msg.author == guild.me and len(msg.embeds) > 0:
                messages.append(msg)
                if len(messages) >= 2:
                    break
        
        if len(messages) >= 2:
            # Edytuj istniejące wiadomości
            await messages[1].edit(embed=embed_on_duty)  # Druga to "Na Służbie"
            await messages[0].edit(embed=embed_off_duty)  # Pierwsza to "Poza Służbą"
        elif len(messages) == 1:
            # Jest tylko jedna, edytuj ją i wyślij drugą
            if "Na Służbie" in messages[0].embeds[0].title:
                await messages[0].edit(embed=embed_on_duty)
            else:
                await messages[0].edit(embed=embed_off_duty)
            await channel.send(embed=embed_off_duty if "Na Służbie" in messages[0].embeds[0].title else embed_on_duty)
        else:
            # Brak wiadomości, wyślij obie
            await channel.send(embed=embed_on_duty)
            await channel.send(embed=embed_off_duty)
    except Exception as e:
        print(f"Błąd podczas aktualizacji statusu: {e}")

# Inicjalizacja bota
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot zalogowany jako {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Zsynchronizowano {len(synced)} komend(y)")
    except Exception as e:
        print(f"Błąd podczas synchronizacji komend: {e}")

@bot.tree.command(name="służba", description="Wejdź/Wyjdź ze służby")
async def sluzba(interaction: discord.Interaction):
    """Komenda - wejście/wyjście ze służby"""
    member = await interaction.guild.fetch_member(interaction.user.id)
    
    best_rank = get_user_best_role(member)
    
    if not best_rank:
        await interaction.response.send_message(
            "❌ Nie posiadasz żadnej roli ze słuzby! Poproś administratora aby przyznał Ci rolę.",
            ephemeral=True
        )
        return
    
    # Sprawdź czy już jest na służbie
    if is_on_duty(interaction.user.id):
        # Usuń ze służby
        remove_from_duty(interaction.user.id)
        await interaction.response.send_message(
            f"👋 Opuściłeś służbę! Twoja ranga: **{best_rank}**",
            ephemeral=True
        )
    else:
        # Dodaj do służby
        add_to_duty(interaction.user.id)
        await interaction.response.send_message(
            f"✅ Weszłeś na służbę! Twoja ranga: **{best_rank}**",
            ephemeral=True
        )
    
    # Aktualizuj status na kanale
    guild = interaction.guild
    channel = guild.get_channel(CHANNEL_ID)
    if channel:
        await update_status_messages(guild, channel)

@bot.tree.command(name="info", description="Informacja o systemie słuzby")
async def info(interaction: discord.Interaction):
    """Wyświetla informacje o systemie"""
    embed = discord.Embed(
        title="📋 Informacja o Systemie Służby",
        description="Dynamiczny system wchodzenia/wychodzenia ze służby!",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Jak to działa:",
        value="Admin przypisuje rolę Discord użytkownikowi. Osoba może wtedy wchodzić i wychodzić ze służby komendą `/służba`.",
        inline=False
    )
    
    embed.add_field(
        name="Dostępne role:",
        value="\n".join([f"• **{rank}**" for rank in sorted(RANKS.keys(), key=lambda r: RANKS[r])]),
        inline=False
    )
    
    embed.add_field(
        name="Komendy użytkownika:",
        value="• `/służba` - Wejdź/Wyjdź ze służby (toggleuj)\n• `/lista_rang` - Pokaż dostępne role\n• `/info` - Tę wiadomość",
        inline=False
    )
    
    embed.add_field(
        name="Komendy admina:",
        value="• `/status` - Odśwież status listy na kanale",
        inline=False
    )
    
    embed.add_field(
        name="Automatyczne:",
        value="• Gdy ktoś opuści serwer - zostaje usunięty ze służby",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="status", description="Wyświetl status służby na kanale")
@discord.app_commands.checks.has_permissions(administrator=True)
async def status(interaction: discord.Interaction):
    """Wysyła/aktualizuje embed ze statusem służby"""
    guild = interaction.guild
    channel = guild.get_channel(CHANNEL_ID)
    
    if not channel:
        await interaction.response.send_message(
            f"❌ Kanał o ID {CHANNEL_ID} nie istnieje!",
            ephemeral=True
        )
        return
    
    await update_status_messages(guild, channel)
    await interaction.response.send_message(
        "✅ Status wysłany/zaktualizowany na kanale!",
        ephemeral=True
    )

@bot.tree.command(name="lista_rang", description="Pokaż dostępne rangi")
async def lista_rang(interaction: discord.Interaction):
    """Wyświetla listę dostępnych rang"""
    embed = discord.Embed(
        title="📊 Dostępne Rangi",
        color=discord.Color.green()
    )
    
    for rank, priority in sorted(RANKS.items(), key=lambda x: x[1]):
        embed.add_field(
            name=rank,
            value=f"Priorytet: {priority}",
            inline=False
        )
    
# Uruchomienie bota
if __name__ == "__main__":
    bot.run(TOKEN)

