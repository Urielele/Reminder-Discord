"""
utils/logger.py — Utilitas logging untuk Discord Task Reminder Bot.

Menyediakan fungsi setup logging ke file dan pengiriman pesan log
ke channel Discord.
"""

import logging

import discord


def setup_logging() -> None:
    """Setup logging ke file discord.log dengan level DEBUG.

    Mengonfigurasi root logger dan logger discord.py untuk menulis ke
    file discord.log dengan format yang mencakup timestamp, level, dan pesan.
    """
    handler = logging.FileHandler(
        filename="discord.log",
        encoding="utf-8",
        mode="a",
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    # Kurangi verbositas library discord.py agar tidak terlalu banyak noise
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


async def log_to_channel(bot: discord.Client, channel_id: str, message: str) -> None:
    """Kirim pesan log ke channel Discord.

    Gagal diam-diam jika channel tidak ditemukan atau terjadi error Discord API,
    sehingga tidak mengganggu operasi utama bot.

    Args:
        bot: Instance Discord bot/client.
        channel_id: ID channel Discord sebagai string.
        message: Pesan yang akan dikirim ke channel.
    """
    if not channel_id:
        return
    try:
        channel = bot.get_channel(int(channel_id))
        if channel is None:
            channel = await bot.fetch_channel(int(channel_id))
        if channel and isinstance(channel, discord.TextChannel):
            await channel.send(message)
    except Exception:
        # Gagal diam-diam — log ke file saja
        logging.getLogger(__name__).debug(
            "Gagal mengirim log ke channel %s.", channel_id
        )
