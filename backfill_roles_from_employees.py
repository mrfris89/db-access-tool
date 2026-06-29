"""
backfill_roles_from_employees.py

SCRIPT SEKALI JALAN (one-time).
Tujuan: generate daftar role di role_master otomatis dari kombinasi
        Divisi + Unit yang sudah ada di employee_master.

Untuk setiap kombinasi (divisi, unit) yang unik:
  - Generate role code (pakai logic SAMA dengan aplikasi: scripts.pick_unique_role_code)
  - Insert 2 role: {DIVISI}_{UNIT}_RO dan {DIVISI}_{UNIT}_RW
  - Kalau role_name sudah ada di role_master -> SKIP (idempotent, aman dijalankan ulang)

Cara jalankan (dari folder app/, di environment yang sama dengan aplikasi):
    python3 backfill_roles_from_employees.py

    atau di dalam container:
    docker exec -it <container_name> python3 backfill_roles_from_employees.py

ENV variable yang dipakai sama dengan aplikasi (DB_HOST, DB_USER, dst, lihat db.py)
"""

import sys
import db
import scripts


def get_or_create_code(cur, conn, name):
    """Sama persis dengan logic di app.py role_suggestion(), supaya kode konsisten."""
    cur.execute("SELECT code FROM role_code_mapping WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute("SELECT code FROM role_code_mapping")
    existing_codes = {r[0] for r in cur.fetchall()}
    new_code = scripts.pick_unique_role_code(name, existing_codes)

    cur.execute(
        "INSERT INTO role_code_mapping (name, code) VALUES (%s, %s)",
        (name, new_code),
    )
    conn.commit()
    return new_code


def main():
    conn = db.get_connection()
    cur = conn.cursor()

    try:
        # 1. Ambil semua kombinasi unik divisi+unit dari employee_master
        cur.execute(
            """
            SELECT DISTINCT divisi, unit
            FROM employee_master
            WHERE divisi != '' AND unit != ''
            ORDER BY divisi, unit
            """
        )
        combos = cur.fetchall()

        if not combos:
            print("Tidak ada data divisi/unit di employee_master. Upload Data Karyawan dulu.")
            return

        print(f"Ditemukan {len(combos)} kombinasi unik Divisi + Unit.\n")

        created = 0
        skipped = 0

        for divisi, unit in combos:
            divisi_code = get_or_create_code(cur, conn, divisi)
            unit_code = get_or_create_code(cur, conn, unit)
            base_role = f"{divisi_code}_{unit_code}"

            for suffix in ("RO", "RW"):
                role_name = f"{base_role}_{suffix}"

                # Cek duplikat dulu (idempotent)
                cur.execute("SELECT id FROM role_master WHERE role_name = %s", (role_name,))
                if cur.fetchone():
                    print(f"  [SKIP] {role_name} sudah ada")
                    skipped += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO role_master (role_name, divisi, unit, suffix, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (role_name, divisi, unit, suffix),
                )
                conn.commit()
                print(f"  [OK]   {role_name}  <-  {divisi} / {unit}")
                created += 1

        print(f"\nSelesai. {created} role baru dibuat, {skipped} role di-skip (sudah ada).")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
