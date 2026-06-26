"""
db.py
Koneksi ke MySQL tracking database.
Konfigurasi diambil dari environment variable (lihat README untuk daftar lengkap).
"""

import os
import mysql.connector
from mysql.connector import pooling

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_NAME = os.environ.get("DB_NAME", "db_access_tracking")
DB_USER = os.environ.get("DB_USER", "app_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

_pool = None


def get_pool():
    """Buat connection pool sekali, dipakai ulang untuk setiap request."""
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="access_tool_pool",
            pool_size=5,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            autocommit=True,
        )
    return _pool


def get_connection():
    """Ambil 1 koneksi dari pool. Caller wajib .close() setelah selesai."""
    return get_pool().get_connection()


def check_connection():
    """Dipakai untuk healthcheck saat startup. Return True/False."""
    try:
        conn = get_connection()
        conn.ping(reconnect=False)
        conn.close()
        return True
    except Exception as e:
        print(f"[DB] Koneksi gagal: {e}")
        return False


def init_schema():
    """
    Membuat tabel jika belum ada. Dipanggil sekali saat startup.
    Tidak menghapus data yang sudah ada (CREATE TABLE IF NOT EXISTS).
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS access_tracking (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                username        VARCHAR(100) NOT NULL,
                nik             VARCHAR(30)  NOT NULL,
                requester       VARCHAR(150) NOT NULL,
                divisi          VARCHAR(150) NOT NULL DEFAULT '',
                unit            VARCHAR(150) NOT NULL,
                subunit         VARCHAR(150) NOT NULL,
                db_type         ENUM('oracle','mysql','postgres') NOT NULL,
                db_host         VARCHAR(150) NOT NULL,
                role_name       VARCHAR(150) NOT NULL,
                host_allowlist  VARCHAR(100) NULL,
                created_at      DATETIME NOT NULL,
                expiry_at       DATETIME NOT NULL,
                status          ENUM('PENDING','ACTIVE','EXTENDED','LOCKED') NOT NULL DEFAULT 'PENDING',
                created_by      VARCHAR(150) NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS employee_master (
                nik           VARCHAR(30)  PRIMARY KEY,
                nama          VARCHAR(150) NOT NULL,
                divisi        VARCHAR(150) NOT NULL DEFAULT '',
                unit          VARCHAR(150) NOT NULL,
                subunit       VARCHAR(150) NOT NULL,
                last_updated  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS role_code_mapping (
                name  VARCHAR(150) PRIMARY KEY,
                code  VARCHAR(3) NOT NULL UNIQUE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS role_master (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                role_name       VARCHAR(150) NOT NULL UNIQUE,
                divisi          VARCHAR(150) NOT NULL,
                unit            VARCHAR(150) NOT NULL,
                suffix          ENUM('RO', 'RW') NOT NULL,
                created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        _migrate_add_last_updated(conn)
        _migrate_add_divisi(conn)
    finally:
        cur.close()
        conn.close()


def _migrate_add_divisi(conn):
    """Migrasi untuk database yang dibuat sebelum kolom divisi ditambahkan."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'employee_master'
              AND COLUMN_NAME = 'divisi'
            """,
            (DB_NAME,),
        )
        exists = cur.fetchone()[0] > 0
        if not exists:
            cur.execute(
                "ALTER TABLE employee_master ADD COLUMN divisi VARCHAR(150) NOT NULL DEFAULT '' AFTER nama"
            )
            conn.commit()
            print("[migration] Kolom divisi ditambahkan ke employee_master")

        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'access_tracking'
              AND COLUMN_NAME = 'divisi'
            """,
            (DB_NAME,),
        )
        exists_tracking = cur.fetchone()[0] > 0
        if not exists_tracking:
            cur.execute(
                "ALTER TABLE access_tracking ADD COLUMN divisi VARCHAR(150) NOT NULL DEFAULT '' AFTER requester"
            )
            conn.commit()
            print("[migration] Kolom divisi ditambahkan ke access_tracking")
    finally:
        cur.close()


def _migrate_add_last_updated(conn):
    """
    Migrasi untuk database yang dibuat sebelum kolom last_updated ditambahkan.
    Aman dijalankan berulang kali (cek dulu sebelum ALTER).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'employee_master'
              AND COLUMN_NAME = 'last_updated'
            """,
            (DB_NAME,),
        )
        exists = cur.fetchone()[0] > 0
        if not exists:
            cur.execute(
                """
                ALTER TABLE employee_master
                ADD COLUMN last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
                """
            )
            conn.commit()
            print("[migration] Kolom last_updated ditambahkan ke employee_master")
    finally:
        cur.close()
