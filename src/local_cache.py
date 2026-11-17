"""
local_cache.py
--------------
قاعدة بيانات SQLite المحلية لتخزين بيانات المواقف أثناء انقطاع الإنترنت.

الجداول:
    readings — كل قراءة مع حالة الإرسال (synced / pending)

الدوال العامة:
    save_reading()   — حفظ قراءة جديدة
    get_unsynced()   — جلب القراءات غير المرسلة
    mark_synced()    — تحديد قراءات كـ"مرسلة"
    get_stats()      — إحصائيات سريعة للتوثيق
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# مسار قاعدة البيانات في جذر المشروع
_DB_PATH = Path(__file__).resolve().parent.parent / "parking_data.db"


def _get_connection() -> sqlite3.Connection:
    """إنشاء اتصال بقاعدة البيانات مع تفعيل WAL للأداء."""
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """إنشاء الجداول إذا لم تكن موجودة (آمنة للاستدعاء المتعدد)."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                spot1       INTEGER NOT NULL,  -- 0=فارغ, 1=مشغول
                spot2       INTEGER NOT NULL,
                spot3       INTEGER NOT NULL,
                spot4       INTEGER NOT NULL,
                occupied    INTEGER NOT NULL,  -- عدد المشغولة
                occupancy   REAL    NOT NULL,  -- نسبة الإشغال %
                synced      INTEGER NOT NULL DEFAULT 0,  -- 0=معلّق, 1=مرسل
                created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_readings_synced
            ON readings (synced, id)
        """)
    logger.info(f"✅ SQLite جاهز: {_DB_PATH}")


def save_reading(states: List[int]) -> int:
    """
    حفظ قراءة جديدة في قاعدة البيانات.

    Args:
        states: قائمة بحالات المواقف [0/1, 0/1, 0/1, 0/1]

    Returns:
        id السجل المُنشأ
    """
    # تأكد من وجود 4 مواقف دائماً
    padded = (states + [1, 1, 1, 1])[:4]
    occupied   = sum(padded)
    occupancy  = round((occupied / 4) * 100, 1)
    timestamp  = datetime.now().isoformat()

    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO readings
                (timestamp, spot1, spot2, spot3, spot4, occupied, occupancy, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (timestamp, padded[0], padded[1], padded[2], padded[3],
             occupied, occupancy)
        )
        row_id = cursor.lastrowid

    logger.debug(f"💾 حُفظ [id={row_id}] | مشغول={occupied}/4 | {occupancy}%")
    return row_id


def get_unsynced(limit: int = 50) -> List[Dict[str, Any]]:
    """
    جلب القراءات غير المُرسلة (synced=0) مرتبة من الأقدم للأحدث.

    Args:
        limit: أقصى عدد سجلات للجلب في دفعة واحدة

    Returns:
        قائمة من القواميس تحتوي بيانات كل قراءة
    """
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM readings WHERE synced = 0 ORDER BY id ASC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def mark_synced(ids: List[int]) -> None:
    """
    تحديد سجلات كـ"مرسلة بنجاح".

    Args:
        ids: قائمة بـ id القراءات المُرسلة
    """
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    with _get_connection() as conn:
        conn.execute(
            f"UPDATE readings SET synced = 1 WHERE id IN ({placeholders})",
            ids
        )
    logger.debug(f"✅ تم تحديد {len(ids)} سجل كـ'مُرسل'")


def get_stats() -> Dict[str, Any]:
    """
    إحصائيات سريعة — مفيدة للتقرير وعرض الحالة.

    Returns:
        dict: {total, synced, pending, avg_occupancy, max_occupancy, min_occupancy}
    """
    with _get_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)                       AS total,
                SUM(synced)                    AS synced,
                SUM(1 - synced)                AS pending,
                ROUND(AVG(occupancy), 1)       AS avg_occupancy,
                MAX(occupancy)                 AS max_occupancy,
                MIN(occupancy)                 AS min_occupancy
            FROM readings
        """).fetchone()
    return dict(row) if row else {}


# تشغيل مباشر للاختبار
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    init_db()
    rid = save_reading([1, 0, 1, 0])
    print(f"حُفظ بـ id={rid}")
    unsynced = get_unsynced()
    print(f"غير مُرسل: {unsynced}")
    mark_synced([rid])
    print(f"إحصائيات: {get_stats()}")
