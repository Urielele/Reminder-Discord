"""
cogs/Reminder.py — Cog untuk menampilkan daftar dan detail tugas kuliah.

Menyediakan perintah untuk melihat semua tugas server dan detail
tugas berdasarkan ID. Data diambil dari database PostgreSQL.

Commands:
    !daftar_tugas      — Tampilkan semua tugas server, urut deadline terdekat
    !tugas <id>        — Tampilkan detail tugas berdasarkan ID
"""

import logging

import discord
from discord.ext import commands

from utils.db import get_tugas_detail, get_tugas_list
from utils.formatter import build_daftar_embed, build_tugas_embed

logger = logging.getLogger(__name__)


class Reminder(commands.Cog):
    """Cog untuk menampilkan daftar dan detail tugas kuliah dari database."""

    def __init__(self, bot: commands.Bot) -> None:
        """Inisialisasi Reminder cog.

        Args:
            bot: Instance Discord bot.
        """
        self.bot = bot

    @commands.command(name="daftar_tugas")
    async def daftar_tugas(self, ctx: commands.Context) -> None:
        """Tampilkan semua tugas yang terdaftar untuk server ini.

        Mengambil semua tugas dari database yang terkait dengan server ini,
        diurutkan berdasarkan deadline terdekat, dan menampilkannya dalam
        format embed Discord.

        Args:
            ctx: Konteks perintah Discord.
        """
        try:
            tugas_list = await get_tugas_list(str(ctx.guild.id))
            embed = build_daftar_embed(tugas_list)
            await ctx.send(embed=embed)
        except Exception as exc:
            logger.error(
                "Gagal mengambil daftar tugas untuk server '%s': %s",
                ctx.guild.name,
                exc,
                exc_info=True,
            )
            await ctx.send("❗ Terjadi kesalahan saat mengambil daftar tugas. Silakan coba lagi.")

    @commands.command(name="tugas")
    async def tugas(self, ctx: commands.Context, id: str = None) -> None:
        """Tampilkan detail tugas berdasarkan ID.

        Mengambil detail satu tugas dari database berdasarkan ID yang diberikan
        dan menampilkannya dalam format embed Discord.

        Args:
            ctx: Konteks perintah Discord.
            id: ID tugas yang ingin dilihat detailnya (harus bilangan bulat positif).
        """
        if id is None:
            await ctx.send("❓ Gunakan **!tugas <ID>**\nContoh: `!tugas 1`")
            return

        # Validasi id adalah bilangan bulat positif
        try:
            id_int = int(id)
            if id_int <= 0:
                raise ValueError("ID harus positif")
        except ValueError:
            await ctx.send("❗ ID harus berupa angka positif. Contoh: `!tugas 1`")
            return

        try:
            tugas_data = await get_tugas_detail(id_int, str(ctx.guild.id))

            if tugas_data is None:
                await ctx.send(f"❗ Tugas dengan ID **{id_int}** tidak ditemukan.")
                return

            embed = build_tugas_embed(tugas_data)
            await ctx.send(embed=embed)

        except Exception as exc:
            logger.error(
                "Gagal mengambil detail tugas ID %s untuk server '%s': %s",
                id_int,
                ctx.guild.name,
                exc,
                exc_info=True,
            )
            await ctx.send("❗ Terjadi kesalahan saat mengambil detail tugas. Silakan coba lagi.")


async def setup(bot: commands.Bot) -> None:
    """Fungsi setup untuk mendaftarkan cog ke bot.

    Args:
        bot: Instance Discord bot.
    """
    await bot.add_cog(Reminder(bot))
