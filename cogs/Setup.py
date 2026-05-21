"""
cogs/Setup.py — Cog untuk registrasi server Discord dan konfigurasi awal.

Menangani event saat bot bergabung ke server baru dan menyediakan perintah
untuk mengonfigurasi channel reminder dan role mention.

Commands:
    !setup <#channel_reminder> <@role_mention> — Konfigurasi channel dan role (admin only)

Events:
    on_guild_join — Auto-register server baru ke database
"""

import logging

import discord
from discord.ext import commands

from utils.db import get_server, upsert_server
from utils.logger import log_to_channel

logger = logging.getLogger(__name__)


class Setup(commands.Cog):
    """Cog untuk registrasi dan konfigurasi awal server Discord."""

    def __init__(self, bot: commands.Bot) -> None:
        """Inisialisasi Setup cog.

        Args:
            bot: Instance Discord bot.
        """
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Event handler saat bot bergabung ke server baru.

        Secara otomatis mendaftarkan server ke database dengan guild_id,
        server_name, dan waktu bergabung.

        Args:
            guild: Objek Guild Discord yang baru dimasuki bot.
        """
        logger.info("Bot bergabung ke server baru: %s (ID: %s)", guild.name, guild.id)
        try:
            await upsert_server(
                guild_id=str(guild.id),
                server_name=guild.name,
            )
            logger.info("Server '%s' berhasil didaftarkan ke database.", guild.name)

            # Log ke channel_log jika sudah dikonfigurasi
            server_data = await get_server(str(guild.id))
            if server_data and server_data.get("channel_log_id"):
                await log_to_channel(
                    self.bot,
                    server_data["channel_log_id"],
                    f"✅ Bot berhasil bergabung dan mendaftarkan server **{guild.name}** ke database.",
                )
        except Exception as exc:
            logger.error(
                "Gagal mendaftarkan server '%s' ke database: %s",
                guild.name,
                exc,
                exc_info=True,
            )

    @commands.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_server(
        self,
        ctx: commands.Context,
        channel_reminder: discord.TextChannel = None,
        role_mention: discord.Role = None,
    ) -> None:
        """Konfigurasi channel reminder dan role mention untuk server ini.

        Hanya dapat dijalankan oleh administrator server. Memperbarui
        channel_reminder_id dan role_mention_id di database.

        Args:
            ctx: Konteks perintah Discord.
            channel_reminder: Channel teks untuk menerima reminder.
            role_mention: Role yang akan di-mention dalam reminder.
        """
        # Validasi jumlah argumen
        if channel_reminder is None or role_mention is None:
            await ctx.send(
                "❗ Penggunaan yang benar: `!setup <#channel_reminder> <@role_mention>`\n"
                "Contoh: `!setup #reminder @Mahasiswa`"
            )
            return

        # Validasi channel ada di server ini
        if channel_reminder.guild.id != ctx.guild.id:
            await ctx.send("❗ Channel tidak ditemukan di server ini.")
            return

        # Validasi role ada di server ini
        if role_mention.guild.id != ctx.guild.id:
            await ctx.send("❗ Role tidak ditemukan di server ini.")
            return

        try:
            await upsert_server(
                guild_id=str(ctx.guild.id),
                server_name=ctx.guild.name,
                channel_reminder_id=str(channel_reminder.id),
                role_mention_id=str(role_mention.id),
            )

            embed = discord.Embed(
                title="✅ Konfigurasi Berhasil",
                description="Server berhasil dikonfigurasi.",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="📢 Channel Reminder",
                value=channel_reminder.mention,
                inline=False,
            )
            embed.add_field(
                name="🏷️ Role Mention",
                value=role_mention.mention,
                inline=False,
            )
            await ctx.send(embed=embed)

            logger.info(
                "Setup berhasil untuk server '%s': channel=%s, role=%s",
                ctx.guild.name,
                channel_reminder.id,
                role_mention.id,
            )

            # Log ke channel_log jika dikonfigurasi
            server_data = await get_server(str(ctx.guild.id))
            if server_data and server_data.get("channel_log_id"):
                await log_to_channel(
                    self.bot,
                    server_data["channel_log_id"],
                    f"⚙️ Perintah `!setup` berhasil dieksekusi oleh {ctx.author.mention}. "
                    f"Channel reminder: {channel_reminder.mention}, Role: {role_mention.mention}.",
                )

        except Exception as exc:
            logger.error("Gagal menyimpan konfigurasi setup: %s", exc, exc_info=True)
            await ctx.send("❗ Terjadi kesalahan saat menyimpan konfigurasi. Silakan coba lagi.")

    @setup_server.error
    async def setup_server_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Handler error untuk perintah !setup.

        Args:
            ctx: Konteks perintah Discord.
            error: Error yang terjadi.
        """
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❗ Perintah ini hanya dapat dijalankan oleh administrator server.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                "❗ Argumen tidak valid. Pastikan channel dan role yang diberikan benar.\n"
                "Penggunaan: `!setup <#channel_reminder> <@role_mention>`"
            )
        else:
            logger.error("Error pada perintah !setup: %s", error, exc_info=True)
            await ctx.send("❗ Terjadi kesalahan yang tidak terduga. Silakan coba lagi.")


async def setup(bot: commands.Bot) -> None:
    """Fungsi setup untuk mendaftarkan cog ke bot.

    Args:
        bot: Instance Discord bot.
    """
    await bot.add_cog(Setup(bot))
