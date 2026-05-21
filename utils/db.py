"""
utils/db.py — Database layer untuk Discord Task Reminder Bot.

Mengelola connection pool asyncpg ke Supabase PostgreSQL dan menyediakan
fungsi-fungsi query helper untuk semua operasi database yang dibutuhkan bot.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

import asyncpg

logger = logging.getLogger(__name__)

# Module-level connection pool
_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    """Inisialisasi connection pool ke Supabase PostgreSQL.

    Membaca SUPABASE_DB_URL dari environment variable. Mencoba koneksi
    sebanyak 3 kali dengan jeda 5 detik di antara setiap percobaan.
    Raise exception jika semua percobaan gagal.
    """
    global _pool
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("SUPABASE_DB_URL tidak ditemukan di environment variables.")

    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            logger.info("Mencoba inisialisasi connection pool (percobaan %d/3)...", attempt)
            _pool = await asyncpg.create_pool(
                dsn=db_url,
                min_size=1,
                max_size=10,
                statement_cache_size=0,  # wajib untuk Supabase Transaction Pooler (pgbouncer)
            )
            logger.info("Connection pool berhasil diinisialisasi.")
            return
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Gagal menginisialisasi connection pool (percobaan %d/3): %s",
                attempt,
                exc,
            )
            if attempt < 3:
                await asyncio.sleep(5)

    raise RuntimeError(
        f"Gagal menginisialisasi connection pool setelah 3 percobaan: {last_exc}"
    ) from last_exc


async def close_pool() -> None:
    """Tutup connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Connection pool ditutup.")


async def get_pool() -> asyncpg.Pool:
    """Kembalikan pool yang sudah diinisialisasi.

    Raises:
        RuntimeError: Jika pool belum diinisialisasi.
    """
    if _pool is None:
        raise RuntimeError("Connection pool belum diinisialisasi. Panggil init_pool() terlebih dahulu.")
    return _pool


async def get_server(guild_id: str) -> dict | None:
    """Ambil data server dari tabel discord_server berdasarkan guild_id.

    Args:
        guild_id: ID guild Discord dalam format string.

    Returns:
        Dictionary berisi data server, atau None jika tidak ditemukan.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM discord_server WHERE guild_id = $1",
        guild_id,
    )
    return dict(row) if row else None


async def upsert_server(
    guild_id: str,
    server_name: str,
    channel_reminder_id: str = None,
    role_mention_id: str = None,
    waktu_reminder: str = None,
    channel_log_id: str = None,
) -> dict:
    """Insert atau update data server di tabel discord_server.

    Menggunakan ON CONFLICT DO UPDATE untuk upsert berdasarkan guild_id.
    Hanya field yang diberikan (tidak None) yang akan diperbarui.

    Args:
        guild_id: ID guild Discord.
        server_name: Nama server Discord.
        channel_reminder_id: ID channel untuk reminder (opsional).
        role_mention_id: ID role yang akan di-mention (opsional).
        waktu_reminder: Mode waktu reminder (opsional).
        channel_log_id: ID channel untuk log (opsional).

    Returns:
        Dictionary berisi data server yang diinsert/diupdate.
    """
    pool = await get_pool()

    # Pastikan row ada dulu (INSERT hanya jika belum ada, tidak overwrite apapun)
    await pool.execute(
        """
        INSERT INTO discord_server (guild_id, server_name, joined_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (guild_id) DO UPDATE SET
            server_name = EXCLUDED.server_name
        """,
        guild_id,
        server_name,
    )

    # Update hanya kolom yang diberikan (tidak None)
    updates = {}
    if channel_reminder_id is not None:
        updates["channel_reminder_id"] = channel_reminder_id
    if role_mention_id is not None:
        updates["role_mention_id"] = role_mention_id
    if waktu_reminder is not None:
        updates["waktu_reminder"] = waktu_reminder
    if channel_log_id is not None:
        updates["channel_log_id"] = channel_log_id

    if updates:
        set_clauses = ", ".join(
            f"{col} = ${i + 2}" for i, col in enumerate(updates.keys())
        )
        values = [guild_id] + list(updates.values())
        await pool.execute(
            f"UPDATE discord_server SET {set_clauses} WHERE guild_id = $1",
            *values,
        )

    row = await pool.fetchrow(
        "SELECT * FROM discord_server WHERE guild_id = $1",
        guild_id,
    )
    return dict(row)


async def get_tugas_list(guild_id: str) -> list[dict]:
    """Ambil semua tugas untuk server tertentu, diurutkan deadline ASC.

    Melakukan JOIN dengan tabel mata_kuliah untuk mendapatkan nama matkul.

    Args:
        guild_id: ID guild Discord.

    Returns:
        List dictionary berisi data tugas, diurutkan berdasarkan deadline terdekat.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT t.id_tugas, t.deadline, t.deskripsi_tugas, t.referensi, t.status,
               mk.judul AS nama_matkul
        FROM tugas t
        JOIN mata_kuliah mk ON mk.id_matkul = t.id_matkul
        JOIN discord_server ds ON ds.id_server = t.id_server
        WHERE ds.guild_id = $1
        ORDER BY t.deadline ASC
        """,
        guild_id,
    )
    return [dict(row) for row in rows]


async def get_tugas_detail(id_tugas: int, guild_id: str) -> dict | None:
    """Ambil detail satu tugas berdasarkan id_tugas dan guild_id.

    Args:
        id_tugas: ID tugas yang dicari.
        guild_id: ID guild Discord untuk memastikan tugas milik server ini.

    Returns:
        Dictionary berisi detail tugas, atau None jika tidak ditemukan.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT t.id_tugas, t.deadline, t.deskripsi_tugas, t.referensi, t.status,
               mk.judul AS nama_matkul
        FROM tugas t
        JOIN mata_kuliah mk ON mk.id_matkul = t.id_matkul
        JOIN discord_server ds ON ds.id_server = t.id_server
        WHERE t.id_tugas = $1
          AND ds.guild_id = $2
        """,
        id_tugas,
        guild_id,
    )
    return dict(row) if row else None


async def get_pending_reminders() -> list[dict]:
    """Ambil semua tugas dengan status='belum' beserta konfigurasi server-nya.

    Digunakan oleh scheduler untuk memeriksa tugas yang perlu diingatkan.
    Hanya mengambil tugas yang deadline-nya belum lewat.

    Returns:
        List dictionary berisi data tugas dan konfigurasi server terkait.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT t.id_tugas, t.deadline, t.deskripsi_tugas, t.referensi, t.status,
               mk.judul AS nama_matkul,
               ds.guild_id, ds.channel_reminder_id, ds.role_mention_id,
               ds.waktu_reminder, ds.channel_log_id
        FROM tugas t
        JOIN mata_kuliah mk ON mk.id_matkul = t.id_matkul
        JOIN discord_server ds ON ds.id_server = t.id_server
        WHERE t.status = 'belum'
          AND t.deadline > NOW()
        ORDER BY t.deadline ASC
        """
    )
    return [dict(row) for row in rows]


async def log_reminder(id_tugas: int, status_kirim: str, pesan_error: str = None) -> None:
    """Catat hasil pengiriman reminder ke tabel reminder_log.

    Args:
        id_tugas: ID tugas yang remindernya dikirim.
        status_kirim: Status pengiriman ('berhasil' atau 'gagal').
        pesan_error: Pesan error jika pengiriman gagal (None jika berhasil).
    """
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO reminder_log (id_tugas, waktu_kirim, status_kirim, pesan_error)
        VALUES ($1, NOW(), $2, $3)
        """,
        id_tugas,
        status_kirim,
        pesan_error,
    )


async def update_status_lewat() -> list[dict]:
    """Update semua tugas yang deadline-nya sudah lewat dan status masih 'belum' menjadi 'lewat'.

    Returns:
        List dictionary berisi tugas yang diupdate, dengan field id_tugas, guild_id,
        dan nama matkul untuk keperluan logging.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        UPDATE tugas
        SET status = 'lewat'
        WHERE deadline < NOW()
          AND status = 'belum'
        RETURNING id_tugas, id_server, id_matkul
        """
    )
    if not rows:
        return []

    # Ambil detail tambahan untuk logging
    result = []
    for row in rows:
        detail = await pool.fetchrow(
            """
            SELECT t.id_tugas, ds.guild_id, mk.judul AS nama_matkul
            FROM tugas t
            JOIN discord_server ds ON ds.id_server = t.id_server
            JOIN mata_kuliah mk ON mk.id_matkul = t.id_matkul
            WHERE t.id_tugas = $1
            """,
            row["id_tugas"],
        )
        if detail:
            result.append(dict(detail))
    return result


async def check_reminder_sent(id_tugas: int, waktu_target: datetime) -> bool:
    """Cek apakah reminder untuk tugas ini sudah dikirim dalam window ±5 menit dari waktu_target.

    Args:
        id_tugas: ID tugas yang diperiksa.
        waktu_target: Waktu target pengiriman reminder.

    Returns:
        True jika reminder sudah dikirim, False jika belum.
    """
    pool = await get_pool()
    window_start = waktu_target - timedelta(minutes=5)
    window_end = waktu_target + timedelta(minutes=5)
    count = await pool.fetchval(
        """
        SELECT COUNT(*) FROM reminder_log
        WHERE id_tugas = $1
          AND status_kirim = 'berhasil'
          AND waktu_kirim >= $2
          AND waktu_kirim <= $3
        """,
        id_tugas,
        window_start,
        window_end,
    )
    return (count or 0) > 0


async def get_daily_summary(guild_id: str) -> dict:
    """Ambil ringkasan aktivitas harian: jumlah reminder berhasil dan gagal sejak 00:00 UTC hari ini.

    Args:
        guild_id: ID guild Discord.

    Returns:
        Dictionary dengan key 'berhasil' dan 'gagal' berisi jumlah masing-masing.
    """
    pool = await get_pool()
    today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    row = await pool.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE rl.status_kirim = 'berhasil') AS berhasil,
            COUNT(*) FILTER (WHERE rl.status_kirim = 'gagal')    AS gagal
        FROM reminder_log rl
        JOIN tugas t ON t.id_tugas = rl.id_tugas
        JOIN discord_server ds ON ds.id_server = t.id_server
        WHERE ds.guild_id = $1
          AND rl.waktu_kirim >= $2
        """,
        guild_id,
        today_utc,
    )
    return {"berhasil": row["berhasil"] or 0, "gagal": row["gagal"] or 0}
