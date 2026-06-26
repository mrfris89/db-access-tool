"""
scripts.py
Generator script SQL untuk provisioning, lock, dan extend.
Aplikasi ini TIDAK pernah eksekusi script ke database target —
hanya generate teks SQL untuk dicopy manual oleh DBA.
"""

import secrets
import string


def generate_password(length=12):
    """Password 12 karakter, crypto-secure, mengandung upper/lower/digit/symbol."""
    upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    lower = "abcdefghijkmnpqrstuvwxyz"
    digits = "23456789"
    special = "!@#%^&*"

    pw_chars = [
        secrets.choice(upper),
        secrets.choice(lower),
        secrets.choice(digits),
        secrets.choice(special),
    ]
    all_chars = upper + lower + digits + special
    pw_chars += [secrets.choice(all_chars) for _ in range(length - len(pw_chars))]

    # shuffle pakai secrets agar tidak predictable
    for i in range(len(pw_chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        pw_chars[i], pw_chars[j] = pw_chars[j], pw_chars[i]

    return "".join(pw_chars)


VOWELS = set("AEIOU")


def generate_role_code_candidates(name: str):
    """
    Generate kandidat kode 3 huruf dari sebuah nama (unit/subunit),
    urut berdasarkan prioritas. Dipakai untuk role name suggestion.
    """
    cleaned = name.replace("&", " ").replace(",", " ")
    words = ["".join(c for c in w if c.isalpha()) for w in cleaned.split()]
    words = [w for w in words if w]
    if not words:
        return ["XXX"]

    candidates = []

    if len(words) >= 3:
        candidates.append(words[0][0] + words[1][0] + words[2][0])
    if len(words) == 2:
        candidates.append(words[0][0] + words[1][:2])
        candidates.append(words[0][:2] + words[1][0])
    if len(words) == 1:
        candidates.append(words[0][:3])

    first = words[0]
    no_vowel = first[0] + "".join(c for c in first[1:] if c.upper() not in VOWELS)
    candidates.append(no_vowel[:3])
    candidates.append(first[:3])

    if len(words) >= 2:
        candidates.append(first[0] + words[1][0] + words[-1][0])

    all_letters = "".join(words)
    if len(all_letters) >= 3:
        candidates.append(all_letters[0] + all_letters[len(all_letters) // 2] + all_letters[-1])

    seen = set()
    out = []
    for c in candidates:
        c = c.upper()[:3]
        if len(c) == 3 and c not in seen:
            seen.add(c)
            out.append(c)
    if not out:
        out.append("XXX")
    return out


def pick_unique_role_code(name: str, existing_codes: set):
    """
    Pilih kode 3 huruf yang belum dipakai (existing_codes) untuk nama ini.
    Dipanggil oleh app.py yang sudah query semua kode terpakai dari DB.
    """
    for cand in generate_role_code_candidates(name):
        if cand not in existing_codes:
            return cand
    # fallback brute-force: kombinasi huruf + angka
    base = generate_role_code_candidates(name)[0][:2]
    for i in range(10):
        trial = (base + str(i))[:3]
        if trial not in existing_codes:
            return trial
    n = 1
    while True:
        trial = f"X{n:02d}"
        if trial not in existing_codes:
            return trial
        n += 1


def to_cidr(allowlist: str) -> str:
    """Konversi input allowlist ke format CIDR. Single IP -> /32."""
    if not allowlist:
        return "0.0.0.0/0"
    trimmed = allowlist.strip()
    if "/" in trimmed:
        return trimmed
    return f"{trimmed}/32"


def quarter_end_date(quarter: str, year: str):
    """Return tuple (display_string, iso_datetime_string) untuk akhir quarter."""
    mapping = {
        "Q1": ("31 Maret", f"{year}-03-31 23:59:59"),
        "Q2": ("30 Juni", f"{year}-06-30 23:59:59"),
        "Q3": ("30 September", f"{year}-09-30 23:59:59"),
        "Q4": ("31 Desember", f"{year}-12-31 23:59:59"),
    }
    label, iso = mapping[quarter]
    return f"{label} {year} 23:59:59", iso


def build_provisioning_script(data: dict, password: str) -> str:
    """
    data wajib punya: dbtype, username, role, allowlist (opsional), expiry_iso
    """
    dbtype = data["dbtype"]
    username = data["username"]
    role = data.get("role", "").strip()
    expiry_iso = data["expiry_iso"]

    if dbtype == "oracle":
        lines = [
            f"-- Oracle: provisioning user {username}",
            f'CREATE USER {username} IDENTIFIED BY "{password}";',
            f"GRANT CONNECT TO {username};",
        ]
        if role:
            lines.append(f"GRANT {role} TO {username};")
        lines.append("-- expiry tracked di tracking DB, bukan native Oracle expiry")
        lines.append(f"-- expiry_at: {expiry_iso}")
        return "\n".join(lines)

    if dbtype == "mysql":
        allowlist = data.get("allowlist", "%").strip() or "%"
        lines = [
            f"-- MySQL: provisioning user {username}",
            f"CREATE USER '{username}'@'{allowlist}' IDENTIFIED BY '{password}';",
        ]
        if role:
            lines.append(f"GRANT {role} TO '{username}'@'{allowlist}';")
        lines.append("FLUSH PRIVILEGES;")
        lines.append(f"-- expiry_at: {expiry_iso} (di-enforce via reminder tool, MySQL tidak native expiry)")
        return "\n".join(lines)

    if dbtype == "postgres":
        allowlist = data.get("allowlist", "")
        cidr = to_cidr(allowlist)
        lines = [
            f"-- PostgreSQL: provisioning user {username}",
            f"CREATE ROLE {username} LOGIN PASSWORD '{password}';",
        ]
        if role:
            lines.append(f"GRANT {role} TO {username};")
        lines.append(f"ALTER ROLE {username} VALID UNTIL '{expiry_iso}';")
        lines.append("-- VALID UNTIL native di PostgreSQL, login otomatis ditolak setelah expiry")
        lines.append("")
        lines.append("-- ===========================================================")
        lines.append("-- PENTING — WAJIB DIJALANKAN MANUAL OLEH DBA, TIDAK OTOMATIS:")
        lines.append("-- Tambahkan entry berikut di pg_hba.conf, lalu reload server:")
        lines.append("-- ===========================================================")
        lines.append(f"-- host    all    {username}    {cidr}    md5")
        lines.append("-- setelah edit pg_hba.conf, jalankan: SELECT pg_reload_conf();")
        return "\n".join(lines)

    return "-- tipe database tidak dikenali"


def build_lock_script(record: dict) -> str:
    dbtype = record["db_type"]
    username = record["username"]

    if dbtype == "postgres":
        return f"-- PostgreSQL: lock user {username}\nALTER ROLE {username} NOLOGIN;"
    if dbtype == "mysql":
        return f"-- MySQL: lock user {username}\nALTER USER '{username}'@'%' ACCOUNT LOCK;"
    if dbtype == "oracle":
        return f"-- Oracle: lock user {username}\nALTER USER {username} ACCOUNT LOCK;"
    return "-- tipe database tidak dikenali"


def build_extend_script(record: dict, new_expiry_iso: str):
    """
    Return None kalau tidak ada script yang perlu dijalankan (MySQL/Oracle saat
    status sebelumnya bukan LOCKED — extend cukup update tracking table saja).
    """
    dbtype = record["db_type"]
    username = record["username"]
    was_locked = record["status"] == "LOCKED"

    if dbtype == "postgres":
        if was_locked:
            return (
                f"-- PostgreSQL: unlock & extend {username}\n"
                f"ALTER ROLE {username} LOGIN;\n"
                f"ALTER ROLE {username} VALID UNTIL '{new_expiry_iso}';"
            )
        return f"-- PostgreSQL: extend expiry {username}\nALTER ROLE {username} VALID UNTIL '{new_expiry_iso}';"

    if dbtype == "mysql":
        if was_locked:
            return f"-- MySQL: unlock {username}\nALTER USER '{username}'@'%' ACCOUNT UNLOCK;"
        return None

    if dbtype == "oracle":
        if was_locked:
            return f"-- Oracle: unlock {username}\nALTER USER {username} ACCOUNT UNLOCK;"
        return None

    return None
