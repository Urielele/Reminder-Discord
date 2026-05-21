"""
utils/formatter.py — Utilitas pemformatan tanggal dan pembuat embed Discord.

Menyediakan fungsi-fungsi untuk memformat data tugas menjadi embed Discord
yang informatif dan konsisten di seluruh bot.
"""

from datetime import datetime

import discord

# Mapping nomor bulan ke nama bulan dalam Bahasa Indonesia
BULAN_ID = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}


def format_deadline(dt: datetime) -> str:
    """Format datetime ke string 'DD Bulan YYYY HH:MM' dalam Bahasa Indonesia.

    Args:
        dt: Objek datetime yang akan diformat.

    Returns:
        String tanggal dalam format 'DD Bulan YYYY HH:MM', contoh: '15 Januari 2025 23:59'.
    """
    bulan = BULAN_ID.get(dt.month, str(dt.month))
    return f"{dt.day:02d} {bulan} {dt.year} {dt.hour:02d}:{dt.minute:02d}"


def build_tugas_embed(tugas: dict) -> discord.Embed:
    """Buat embed detail untuk satu tugas (!tugas <id>).

    Menampilkan informasi lengkap satu tugas termasuk mata kuliah, deskripsi,
    deadline, referensi, dan status.

    Args:
        tugas: Dictionary berisi data tugas dari database.
               Key yang dibutuhkan: nama_matkul, deskripsi_tugas, deadline,
               referensi, status, id_tugas.

    Returns:
        Objek discord.Embed berisi detail tugas.
    """
    status = tugas.get("status", "belum")
    color = discord.Color.red() if status == "lewat" else discord.Color.blue()

    embed = discord.Embed(
        title=f"📋 Detail Tugas — {tugas.get('nama_matkul', '-')}",
        color=color,
    )

    embed.add_field(
        name="📚 Mata Kuliah",
        value=tugas.get("nama_matkul", "-"),
        inline=False,
    )
    embed.add_field(
        name="📝 Deskripsi",
        value=tugas.get("deskripsi_tugas") or "-",
        inline=False,
    )

    deadline = tugas.get("deadline")
    deadline_str = format_deadline(deadline) if deadline else "-"
    embed.add_field(
        name="📅 Deadline",
        value=deadline_str,
        inline=True,
    )

    embed.add_field(
        name="🔗 Referensi",
        value=tugas.get("referensi") or "-",
        inline=True,
    )

    status_display = {
        "belum": "⏳ Belum",
        "selesai": "✅ Selesai",
        "lewat": "❌ Lewat",
    }.get(status, status)
    embed.add_field(
        name="📌 Status",
        value=status_display,
        inline=True,
    )

    embed.set_footer(text=f"ID Tugas: {tugas.get('id_tugas', '-')}")
    return embed


def build_daftar_embed(tugas_list: list[dict]) -> discord.Embed:
    """Buat embed daftar tugas (!daftar_tugas).

    Menampilkan semua tugas server dalam satu embed, diurutkan berdasarkan
    deadline terdekat. Tugas yang sudah lewat diberi prefiks [LEWAT].

    Args:
        tugas_list: List dictionary berisi data tugas dari database.
                    Setiap dict membutuhkan: status, nama_matkul, id_tugas, deadline.

    Returns:
        Objek discord.Embed berisi daftar tugas.
    """
    embed = discord.Embed(
        title="📚 Daftar Tugas",
        color=discord.Color.blue(),
    )

    if not tugas_list:
        embed.description = "Belum ada tugas yang terdaftar untuk server ini."
        return embed

    for tugas in tugas_list:
        status = tugas.get("status", "belum")
        nama_matkul = tugas.get("nama_matkul", "-")
        id_tugas = tugas.get("id_tugas", "-")

        if status == "lewat":
            field_name = f"[LEWAT] {nama_matkul} (ID: {id_tugas})"
        else:
            field_name = f"{nama_matkul} (ID: {id_tugas})"

        deadline = tugas.get("deadline")
        deadline_str = format_deadline(deadline) if deadline else "-"

        embed.add_field(
            name=field_name,
            value=f"🕒 {deadline_str}",
            inline=False,
        )

    return embed


def build_info_server_embed(server: dict) -> discord.Embed:
    """Buat embed info konfigurasi server (!info_server).

    Menampilkan konfigurasi server saat ini termasuk channel reminder,
    role mention, waktu reminder, dan channel log.

    Args:
        server: Dictionary berisi data konfigurasi server dari database.
                Key yang dibutuhkan: channel_reminder_id, role_mention_id,
                waktu_reminder, channel_log_id, server_name.

    Returns:
        Objek discord.Embed berisi informasi konfigurasi server.
    """
    embed = discord.Embed(
        title=f"⚙️ Konfigurasi Server — {server.get('server_name', '-')}",
        color=discord.Color.green(),
    )

    channel_reminder = server.get("channel_reminder_id")
    embed.add_field(
        name="📢 Channel Reminder",
        value=f"<#{channel_reminder}>" if channel_reminder else "belum dikonfigurasi",
        inline=False,
    )

    role_mention = server.get("role_mention_id")
    embed.add_field(
        name="🏷️ Role Mention",
        value=f"<@&{role_mention}>" if role_mention else "belum dikonfigurasi",
        inline=False,
    )

    waktu_reminder = server.get("waktu_reminder")
    embed.add_field(
        name="⏰ Waktu Reminder",
        value=waktu_reminder if waktu_reminder else "belum dikonfigurasi",
        inline=False,
    )

    channel_log = server.get("channel_log_id")
    embed.add_field(
        name="📋 Channel Log",
        value=f"<#{channel_log}>" if channel_log else "belum dikonfigurasi",
        inline=False,
    )

    return embed


def build_reminder_embed(tugas: dict) -> discord.Embed:
    """Buat embed untuk pesan reminder otomatis.

    Digunakan oleh Scheduler saat mengirim reminder ke channel reminder.

    Args:
        tugas: Dictionary berisi data tugas dari database.
               Key yang dibutuhkan: nama_matkul, deskripsi_tugas, deadline, referensi.

    Returns:
        Objek discord.Embed berisi informasi reminder.
    """
    embed = discord.Embed(
        title="🔔 Reminder Tugas",
        description="Jangan lupa kerjakan tugasmu!",
        color=discord.Color.orange(),
    )

    embed.add_field(
        name="📚 Mata Kuliah",
        value=tugas.get("nama_matkul", "-"),
        inline=False,
    )
    embed.add_field(
        name="📝 Deskripsi",
        value=tugas.get("deskripsi_tugas") or "-",
        inline=False,
    )

    deadline = tugas.get("deadline")
    deadline_str = format_deadline(deadline) if deadline else "-"
    embed.add_field(
        name="📅 Deadline",
        value=deadline_str,
        inline=True,
    )

    embed.add_field(
        name="🔗 Referensi",
        value=tugas.get("referensi") or "-",
        inline=True,
    )

    embed.set_footer(text=f"ID Tugas: {tugas.get('id_tugas', '-')}")
    return embed


def build_daily_summary_embed(summary: dict) -> discord.Embed:
    """Buat embed ringkasan aktivitas harian.

    Menampilkan jumlah reminder yang berhasil dan gagal dikirim hari ini.

    Args:
        summary: Dictionary berisi data ringkasan harian.
                 Key yang dibutuhkan: 'berhasil' dan 'gagal'.

    Returns:
        Objek discord.Embed berisi ringkasan aktivitas harian.
    """
    embed = discord.Embed(
        title="📊 Ringkasan Aktivitas Harian",
        description="Laporan aktivitas bot hari ini (00:00 UTC).",
        color=discord.Color.purple(),
    )

    embed.add_field(
        name="✅ Reminder Berhasil",
        value=str(summary.get("berhasil", 0)),
        inline=True,
    )
    embed.add_field(
        name="❌ Reminder Gagal",
        value=str(summary.get("gagal", 0)),
        inline=True,
    )

    return embed
