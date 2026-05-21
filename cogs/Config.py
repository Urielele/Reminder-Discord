"""
cogs/Config.py — Cog untuk konfigurasi waktu reminder dan info server.

Menyediakan perintah untuk mengatur mode waktu pengiriman reminder
dan menampilkan konfigurasi server saat ini.

Commands:
    !set_reminder <mode> — Set mode waktu reminder (admin only)
    !info_server         — Tampilkan konfigurasi server saat ini
"""

import logging

import discord
from discord.ext import commands

from utils.db import get_server, upsert_server
from utils.formatter import build_info_server_embed
from utils.logger import log_to_channel

logger = logging.getLogger(__name__)

# Mode waktu reminder yang valid
VALID_MODES = ["1_hari_sebelum", "2_hari_sebelum", "malam_sebelum"]


class Config(commands.Cog):
    """Cog untuk konfigurasi waktu reminder dan informasi server."""

    def __init__(self, bot: commands.Bot) -> None:
        """Inisialisasi Config cog.

        Args:
            bot: Instance Discord bot.
        """
        self.bot = bot

    @commands.command(name="set_reminder")
    @commands.has_permissions(administrator=True)
    async def set_reminder(self, ctx: commands.Context, mode: str = None) -> None:
        """Set mode waktu pengiriman reminder untuk server ini.

        Hanya dapat dijalankan oleh administrator server. Mode yang valid:
        1_hari_sebelum, 2_hari_sebelum, malam_sebelum.

        Args:
            ctx: Konteks perintah Discord.
            mode: Mode waktu reminder yang dipilih.
        """
        if mode is None:
            await ctx.send(
                f"❗ Penggunaan: `!set_reminder <mode>`\n"
                f"Mode yang valid: `{'`, `'.join(VALID_MODES)}`"
            )
            return

        if mode not in VALID_MODES:
            await ctx.send(
                f"❗ Mode tidak valid: `{mode}`\n"
                f"Mode yang tersedia: `{'`, `'.join(VALID_MODES)}`"
            )
            return

        try:
            await upsert_server(
                guild_id=str(ctx.guild.id),
                server_name=ctx.guild.name,
                waktu_reminder=mode,
            )

            embed = discord.Embed(
                title="✅ Mode Reminder Diperbarui",
                description=f"Mode reminder sekarang: **{mode}**",
                color=discord.Color.green(),
            )
            await ctx.send(embed=embed)

            logger.info(
                "Mode reminder diperbarui untuk server '%s': %s",
                ctx.guild.name,
                mode,
            )

            # Log ke channel_log jika dikonfigurasi
            server_data = await get_server(str(ctx.guild.id))
            if server_data and server_data.get("channel_log_id"):
                await log_to_channel(
                    self.bot,
                    server_data["channel_log_id"],
                    f"⚙️ Perintah `!set_reminder` berhasil dieksekusi oleh {ctx.author.mention}. "
                    f"Mode reminder baru: **{mode}**.",
                )

        except Exception as exc:
            logger.error(
                "Gagal memperbarui mode reminder untuk server '%s': %s",
                ctx.guild.name,
                exc,
                exc_info=True,
            )
            await ctx.send(
                "❗ Konfigurasi gagal disimpan. Silakan coba lagi."
            )

    @set_reminder.error
    async def set_reminder_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Handler error untuk perintah !set_reminder.

        Args:
            ctx: Konteks perintah Discord.
            error: Error yang terjadi.
        """
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❗ Perintah ini hanya dapat dijalankan oleh administrator server.")
        else:
            logger.error("Error pada perintah !set_reminder: %s", error, exc_info=True)
            await ctx.send("❗ Terjadi kesalahan yang tidak terduga. Silakan coba lagi.")

    @commands.command(name="info_server")
    async def info_server(self, ctx: commands.Context) -> None:
        """Tampilkan konfigurasi server saat ini dalam format embed.

        Menampilkan channel reminder, role mention, waktu reminder, dan
        channel log. Field yang belum dikonfigurasi ditampilkan sebagai
        'belum dikonfigurasi'.

        Args:
            ctx: Konteks perintah Discord.
        """
        try:
            server_data = await get_server(str(ctx.guild.id))

            if server_data is None:
                await ctx.send(
                    "❗ Server ini belum terdaftar. Gunakan `!setup` untuk mendaftarkan server."
                )
                return

            # Tambahkan server_name ke data jika belum ada
            if "server_name" not in server_data or not server_data["server_name"]:
                server_data["server_name"] = ctx.guild.name

            embed = build_info_server_embed(server_data)
            await ctx.send(embed=embed)

        except Exception as exc:
            logger.error(
                "Gagal mengambil info server '%s': %s",
                ctx.guild.name,
                exc,
                exc_info=True,
            )
            await ctx.send("❗ Terjadi kesalahan saat mengambil informasi server. Silakan coba lagi.")


async def setup(bot: commands.Bot) -> None:
    """Fungsi setup untuk mendaftarkan cog ke bot.

    Args:
        bot: Instance Discord bot.
    """
    await bot.add_cog(Config(bot))
