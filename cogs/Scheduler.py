"""
cogs/Scheduler.py — Cog untuk pengiriman reminder otomatis dan pembaruan status tugas.

Menjalankan background task yang memeriksa tugas setiap 60 menit,
mengirim reminder ke channel yang dikonfigurasi, dan memperbarui
status tugas yang sudah melewati deadline.

Background Tasks:
    check_reminders — Loop setiap 60 menit:
        1. Update status tugas yang sudah lewat deadline
        2. Kirim reminder untuk tugas yang mendekati deadline
        3. Kirim daily summary jam 00:00 UTC

Reminder Modes:
    1_hari_sebelum  — Kirim 24 jam sebelum deadline (jam sama dengan deadline)
    2_hari_sebelum  — Kirim 48 jam sebelum deadline (jam sama dengan deadline)
    malam_sebelum   — Kirim jam 20:00 malam sebelum hari deadline
"""

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from utils.db import (
    check_reminder_sent,
    get_daily_summary,
    get_pending_reminders,
    log_reminder,
    update_status_lewat,
)
from utils.formatter import build_daily_summary_embed, build_reminder_embed
from utils.logger import log_to_channel

logger = logging.getLogger(__name__)


def calculate_waktu_target(deadline: datetime, mode: str) -> datetime:
    """Hitung waktu target pengiriman reminder berdasarkan mode dan deadline.

    Args:
        deadline: Waktu deadline tugas (timezone-aware).
        mode: Mode waktu reminder ('1_hari_sebelum', '2_hari_sebelum', 'malam_sebelum').

    Returns:
        Datetime waktu target pengiriman reminder (timezone-aware).
    """
    if mode == "1_hari_sebelum":
        return deadline - timedelta(days=1)
    elif mode == "2_hari_sebelum":
        return deadline - timedelta(days=2)
    elif mode == "malam_sebelum":
        prev_day = deadline.date() - timedelta(days=1)
        return datetime(
            prev_day.year,
            prev_day.month,
            prev_day.day,
            20,
            0,
            0,
            tzinfo=deadline.tzinfo,
        )
    else:
        # Default: 1 hari sebelum
        return deadline - timedelta(days=1)


class Scheduler(commands.Cog):
    """Cog untuk background task pengiriman reminder dan pembaruan status tugas."""

    def __init__(self, bot: commands.Bot) -> None:
        """Inisialisasi Scheduler cog dan mulai background task.

        Args:
            bot: Instance Discord bot.
        """
        self.bot = bot
        self.check_reminders.start()

    def cog_unload(self) -> None:
        """Hentikan background task saat cog di-unload."""
        self.check_reminders.cancel()

    @tasks.loop(minutes=60)
    async def check_reminders(self) -> None:
        """Background task utama yang berjalan setiap 60 menit.

        Melakukan tiga hal dalam setiap siklus:
        1. Memperbarui status tugas yang sudah melewati deadline menjadi 'lewat'.
        2. Memeriksa dan mengirim reminder untuk tugas yang mendekati waktu target.
        3. Mengirim daily summary ke channel log pada jam 00:00 UTC.
        """
        logger.info("Scheduler: memulai siklus pemeriksaan reminder.")

        # Langkah 1: Update status tugas yang sudah lewat deadline
        await self._update_expired_tasks()

        # Langkah 2: Kirim reminder untuk tugas yang mendekati deadline
        await self._send_pending_reminders()

        # Langkah 3: Kirim daily summary jika jam 00:00 UTC
        await self._send_daily_summaries()

        logger.info("Scheduler: siklus pemeriksaan selesai.")

    @check_reminders.before_loop
    async def before_check_reminders(self) -> None:
        """Tunggu bot siap sebelum memulai background task."""
        await self.bot.wait_until_ready()
        logger.info("Scheduler: background task siap dimulai.")

    async def _update_expired_tasks(self) -> None:
        """Perbarui status tugas yang sudah melewati deadline menjadi 'lewat'.

        Mencatat perubahan ke channel log jika dikonfigurasi.
        """
        try:
            updated_tasks = await update_status_lewat()
            if updated_tasks:
                logger.info(
                    "Scheduler: %d tugas diperbarui statusnya menjadi 'lewat'.",
                    len(updated_tasks),
                )
                # Log ke channel_log masing-masing server
                for tugas in updated_tasks:
                    guild_id = tugas.get("guild_id")
                    if not guild_id:
                        continue
                    guild = self.bot.get_guild(int(guild_id))
                    if guild is None:
                        continue
                    # Ambil channel_log dari server data
                    from utils.db import get_server
                    server_data = await get_server(guild_id)
                    if server_data and server_data.get("channel_log_id"):
                        await log_to_channel(
                            self.bot,
                            server_data["channel_log_id"],
                            f"📌 Status tugas **{tugas.get('nama_matkul', '-')}** "
                            f"(ID: {tugas.get('id_tugas', '-')}) diperbarui menjadi **lewat**.",
                        )
        except Exception as exc:
            logger.error(
                "Scheduler: gagal memperbarui status tugas lewat: %s",
                exc,
                exc_info=True,
            )

    async def _send_pending_reminders(self) -> None:
        """Periksa dan kirim reminder untuk tugas yang mendekati waktu target.

        Untuk setiap tugas dengan status 'belum', hitung waktu target berdasarkan
        mode reminder server, lalu kirim jika sekarang dalam window ±5 menit.
        """
        try:
            pending = await get_pending_reminders()
            now = datetime.now(timezone.utc)

            for tugas in pending:
                mode = tugas.get("waktu_reminder") or "1_hari_sebelum"
                deadline = tugas.get("deadline")

                if deadline is None:
                    continue

                # Pastikan deadline timezone-aware
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)

                waktu_target = calculate_waktu_target(deadline, mode)

                # Cek apakah sekarang dalam window ±5 menit dari waktu_target
                diff = abs((now - waktu_target).total_seconds())
                if diff > 300:  # 5 menit = 300 detik
                    continue

                id_tugas = tugas.get("id_tugas")
                channel_reminder_id = tugas.get("channel_reminder_id")
                role_mention_id = tugas.get("role_mention_id")
                guild_id = tugas.get("guild_id")

                if not channel_reminder_id:
                    logger.warning(
                        "Scheduler: tugas ID %s tidak memiliki channel_reminder_id, dilewati.",
                        id_tugas,
                    )
                    continue

                # Cek duplikat — apakah reminder sudah dikirim dalam window ini
                already_sent = await check_reminder_sent(id_tugas, waktu_target)
                if already_sent:
                    logger.debug(
                        "Scheduler: reminder untuk tugas ID %s sudah dikirim, dilewati.",
                        id_tugas,
                    )
                    continue

                # Kirim reminder
                await self._send_reminder(
                    tugas=tugas,
                    channel_reminder_id=channel_reminder_id,
                    role_mention_id=role_mention_id,
                    guild_id=guild_id,
                )

        except Exception as exc:
            logger.error(
                "Scheduler: gagal memproses pending reminders: %s",
                exc,
                exc_info=True,
            )

    async def _send_reminder(
        self,
        tugas: dict,
        channel_reminder_id: str,
        role_mention_id: str | None,
        guild_id: str,
    ) -> None:
        """Kirim satu pesan reminder ke channel yang dikonfigurasi.

        Args:
            tugas: Dictionary berisi data tugas.
            channel_reminder_id: ID channel tujuan reminder.
            role_mention_id: ID role yang akan di-mention (opsional).
            guild_id: ID guild Discord.
        """
        id_tugas = tugas.get("id_tugas")
        channel_log_id = tugas.get("channel_log_id")

        try:
            channel = self.bot.get_channel(int(channel_reminder_id))
            if channel is None:
                channel = await self.bot.fetch_channel(int(channel_reminder_id))

            if channel is None or not isinstance(channel, discord.TextChannel):
                raise ValueError(f"Channel {channel_reminder_id} tidak ditemukan atau bukan TextChannel.")

            embed = build_reminder_embed(tugas)
            mention_str = f"<@&{role_mention_id}>" if role_mention_id else ""
            content = mention_str if mention_str else None

            await channel.send(content=content, embed=embed)

            # Catat ke reminder_log sebagai berhasil
            await log_reminder(id_tugas=id_tugas, status_kirim="berhasil")
            logger.info(
                "Scheduler: reminder berhasil dikirim untuk tugas ID %s ke channel %s.",
                id_tugas,
                channel_reminder_id,
            )

            # Log ke channel_log
            if channel_log_id:
                await log_to_channel(
                    self.bot,
                    channel_log_id,
                    f"✅ Reminder berhasil dikirim untuk tugas **{tugas.get('nama_matkul', '-')}** "
                    f"(ID: {id_tugas}).",
                )

        except discord.HTTPException as exc:
            error_msg = str(exc)
            await log_reminder(
                id_tugas=id_tugas,
                status_kirim="gagal",
                pesan_error=error_msg,
            )
            logger.error(
                "Scheduler: gagal mengirim reminder untuk tugas ID %s (Discord API error): %s",
                id_tugas,
                error_msg,
            )
            if channel_log_id:
                await log_to_channel(
                    self.bot,
                    channel_log_id,
                    f"❌ Reminder gagal dikirim untuk tugas **{tugas.get('nama_matkul', '-')}** "
                    f"(ID: {id_tugas}). Error: {error_msg}",
                )

        except Exception as exc:
            error_msg = str(exc)
            await log_reminder(
                id_tugas=id_tugas,
                status_kirim="gagal",
                pesan_error=error_msg,
            )
            logger.error(
                "Scheduler: gagal mengirim reminder untuk tugas ID %s: %s",
                id_tugas,
                error_msg,
                exc_info=True,
            )

    async def _send_daily_summaries(self) -> None:
        """Kirim ringkasan aktivitas harian ke semua channel log yang dikonfigurasi.

        Hanya dikirim jika jam sekarang adalah 00:00 UTC (dalam window 60 menit pertama hari baru).
        """
        now = datetime.now(timezone.utc)
        # Cek apakah sekarang dalam 60 menit pertama hari baru (00:00 - 01:00 UTC)
        if now.hour != 0:
            return

        logger.info("Scheduler: mengirim daily summary untuk semua server.")

        for guild in self.bot.guilds:
            try:
                from utils.db import get_server
                server_data = await get_server(str(guild.id))
                if not server_data or not server_data.get("channel_log_id"):
                    continue

                summary = await get_daily_summary(str(guild.id))
                embed = build_daily_summary_embed(summary)

                channel_log_id = server_data["channel_log_id"]
                channel = self.bot.get_channel(int(channel_log_id))
                if channel is None:
                    channel = await self.bot.fetch_channel(int(channel_log_id))

                if channel and isinstance(channel, discord.TextChannel):
                    await channel.send(embed=embed)
                    logger.info(
                        "Scheduler: daily summary berhasil dikirim ke server '%s'.",
                        guild.name,
                    )

            except Exception as exc:
                logger.error(
                    "Scheduler: gagal mengirim daily summary untuk server '%s': %s",
                    guild.name,
                    exc,
                    exc_info=True,
                )


async def setup(bot: commands.Bot) -> None:
    """Fungsi setup untuk mendaftarkan cog ke bot.

    Args:
        bot: Instance Discord bot.
    """
    await bot.add_cog(Scheduler(bot))
