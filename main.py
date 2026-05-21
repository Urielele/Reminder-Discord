"""
main.py — Entry point Discord Task Reminder Bot.

Startup sequence:
1. Load .env
2. Setup logging
3. Init DB connection pool (verifikasi SELECT 1)
4. Verifikasi akses tabel wajib
5. Load semua cogs dari folder cogs/
6. Start bot

Jika DB gagal → log error → sys.exit(1)
"""

import asyncio
import logging
import os
import sys
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.db import close_pool, get_pool, init_pool
from utils.logger import setup_logging

# Tabel yang wajib dapat diakses saat startup
REQUIRED_TABLES = ["tugas", "mata_kuliah", "discord_server", "reminder_log"]


async def verify_database() -> None:
    """Verifikasi koneksi dan akses tabel database.

    Menjalankan SELECT 1 untuk memverifikasi koneksi, kemudian memeriksa
    akses ke semua tabel yang diperlukan bot.

    Raises:
        RuntimeError: Jika koneksi atau akses tabel gagal.
    """
    logger = logging.getLogger(__name__)
    pool = await get_pool()

    # Verifikasi koneksi dasar
    await pool.fetchval("SELECT 1")
    logger.info("Verifikasi koneksi database berhasil.")

    # Verifikasi akses tabel wajib
    for table in REQUIRED_TABLES:
        try:
            await pool.fetchval(f"SELECT COUNT(*) FROM {table} LIMIT 1")
            logger.info("Akses tabel '%s' berhasil.", table)
        except Exception as exc:
            raise RuntimeError(
                f"Tidak dapat mengakses tabel '{table}': {exc}"
            ) from exc


async def load_cogs(bot: commands.Bot) -> None:
    """Load semua cog dari folder cogs/.

    Memuat setiap file .py di folder cogs/ sebagai ekstensi bot,
    kecuali file yang dimulai dengan underscore.

    Args:
        bot: Instance Discord bot.
    """
    logger = logging.getLogger(__name__)
    cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")

    for filename in os.listdir(cogs_dir):
        if filename.endswith(".py") and not filename.startswith("_"):
            cog_name = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(cog_name)
                logger.info("Cog '%s' berhasil dimuat.", cog_name)
            except Exception as exc:
                logger.error(
                    "Gagal memuat cog '%s': %s",
                    cog_name,
                    exc,
                    exc_info=True,
                )


async def main() -> None:
    """Fungsi utama untuk menjalankan bot.

    Menjalankan startup sequence lengkap: setup logging, inisialisasi DB,
    verifikasi tabel, load cogs, dan start bot.
    """
    # 1. Load environment variables
    load_dotenv()

    # 2. Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== Discord Task Reminder Bot starting ===")

    # Ambil token Discord
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.critical("DISCORD_TOKEN tidak ditemukan di environment variables.")
        sys.exit(1)

    # 3. Inisialisasi connection pool database
    try:
        await init_pool()
    except Exception as exc:
        logger.critical("Gagal menginisialisasi database: %s", exc, exc_info=True)
        sys.exit(1)

    # 4. Verifikasi koneksi dan akses tabel
    try:
        await verify_database()
    except Exception as exc:
        logger.critical("Verifikasi database gagal: %s", exc, exc_info=True)
        await close_pool()
        sys.exit(1)

    # Setup intents bot
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    # Global error handler
    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
        """Handler global untuk error perintah yang tidak tertangani.

        Mengirim pesan generik ke channel (tanpa detail teknis) dan
        mencatat stack trace lengkap ke discord.log.

        Args:
            ctx: Konteks perintah Discord.
            error: Error yang terjadi.
        """
        # Abaikan error yang sudah ditangani di level cog
        if hasattr(error, "handled") and error.handled:
            return

        # Abaikan CommandNotFound agar tidak spam
        if isinstance(error, commands.CommandNotFound):
            return

        # Catat stack trace lengkap ke log
        logger.error(
            "Error tidak tertangani pada perintah '%s' di server '%s': %s\n%s",
            ctx.command,
            ctx.guild.name if ctx.guild else "DM",
            error,
            "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        )

        # Kirim pesan generik ke channel (tanpa stack trace / detail teknis)
        await ctx.send("❗ Terjadi kesalahan saat memproses perintah. Silakan coba lagi.")

    @bot.event
    async def on_ready() -> None:
        """Event handler saat bot siap terhubung ke Discord."""
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="!help",
            )
        )
        logger.info("Bot '%s' siap. Terhubung ke %d server.", bot.user.name, len(bot.guilds))
        print(f"{bot.user.name.upper()} IS READY :D")

    # 5. Load semua cogs
    await load_cogs(bot)

    # 6. Start bot
    try:
        async with bot:
            await bot.start(token)
    except Exception as exc:
        logger.critical("Bot berhenti karena error: %s", exc, exc_info=True)
    finally:
        await close_pool()
        logger.info("=== Discord Task Reminder Bot stopped ===")


if __name__ == "__main__":
    asyncio.run(main())
