"""
cogs/Greetings.py — Cog untuk perintah sapaan dasar.

Menyediakan perintah sederhana untuk menyapa pengguna Discord.

Commands:
    !hello — Kirim sapaan ke pengguna yang memanggil perintah
"""

import discord
from discord.ext import commands


class Greetings(commands.Cog):
    """Cog untuk perintah sapaan dasar bot."""

    def __init__(self, bot: commands.Bot) -> None:
        """Inisialisasi Greetings cog.

        Args:
            bot: Instance Discord bot.
        """
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Event handler saat bot siap. Mencetak status ke konsol."""
        print("Greetings.py is ready")

    @commands.command(name="hello")
    async def hello(self, ctx: commands.Context) -> None:
        """Kirim sapaan ke pengguna yang memanggil perintah.

        Args:
            ctx: Konteks perintah Discord.
        """
        await ctx.send(f"Hello {ctx.author.mention}!")


async def setup(bot: commands.Bot) -> None:
    """Fungsi setup untuk mendaftarkan cog ke bot.

    Args:
        bot: Instance Discord bot.
    """
    await bot.add_cog(Greetings(bot))
