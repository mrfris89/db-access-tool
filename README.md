# DB Access Provisioning Tool

Tools internal untuk DBA — generate script provisioning/lock/extend user akses
database (Oracle/MySQL/PostgreSQL), dengan reminder berbasis tracking table
di MySQL. Aplikasi ini **tidak pernah** connect atau eksekusi apapun ke
database target — semua script di-generate untuk dicopy manual oleh DBA.

## Arsitektur

```
[1 Docker Container: app]  ----->  [MySQL tracking, sudah ada/eksternal]
   - Flask + Gunicorn
   - Port 5010
   - Tidak ada login/auth
```

Database tracking **tidak ikut di-deploy lewat container ini** — sudah ada
dan dikelola terpisah. Aplikasi hanya connect via environment variable.

## 1. Siapkan Database Tracking (MySQL)

Buat database dan user khusus untuk aplikasi ini (jangan pakai root):

```sql
CREATE DATABASE db_access_tracking CHARACTER SET utf8mb4;
CREATE USER 'app_user'@'%' IDENTIFIED BY 'password_aman_kamu';
GRANT SELECT, INSERT, UPDATE, DELETE ON db_access_tracking.* TO 'app_user'@'%';
FLUSH PRIVILEGES;
```

Aplikasi akan otomatis membuat tabel (`access_tracking`, `employee_master`)
saat pertama kali start (`CREATE TABLE IF NOT EXISTS`) — tidak perlu migration
manual. Tapi kalau mau buat manual duluan, schema-nya ada di `db.py`.

## 2. Build Image

```bash
cd app/
docker build -t db-access-tool:latest .
```

## 3. Konfigurasi Environment Variable

Salin `.env.example` jadi `.env`, isi sesuai database tracking kamu:

```bash
cp .env.example .env
nano .env
```

Isi minimal:
```
DB_HOST=10.20.30.100
DB_PORT=3306
DB_NAME=db_access_tracking
DB_USER=app_user
DB_PASSWORD=password_aman_kamu
APP_PORT=5010
```

**Jangan commit file `.env` yang sudah terisi ke git.**

## 4. Jalankan Container

```bash
docker run -d \
  --name db-access-tool \
  -p 5010:5010 \
  --env-file .env \
  db-access-tool:latest
```

Akses dari browser: `http://<host-server>:5010`

## 5. Cek Kesehatan Aplikasi

```bash
curl http://localhost:5010/healthz
```

Response `{"db_connected": true}` artinya koneksi database OK.
Kalau `false`, cek kembali environment variable / network ke database.

## 6. Query Reminder (untuk tools eksternal kamu)

Tools reminder eksternal kamu cukup query langsung ke database tracking
(tabel `access_tracking`), **tidak lewat aplikasi ini**:

```sql
SELECT
    id, username, requester, db_type, db_host, expiry_at, status
FROM access_tracking
WHERE expiry_at <= NOW()
  AND status IN ('ACTIVE', 'EXTENDED')
ORDER BY expiry_at ASC;
```

Jalankan query ini 1x sehari. Selama DBA belum update status record secara
manual (lewat Dashboard), row yang sudah lewat expiry akan **selalu muncul**
di hasil query — sesuai desain reminder yang terus-menerus mengingatkan.

## Struktur Project

```
app/
├── app.py              # Flask app, semua route API
├── db.py                # Koneksi MySQL (pool), baca config dari env var
├── scripts.py           # Generator script SQL (provisioning/lock/extend)
├── requirements.txt
├── Dockerfile
├── .env.example
├── .dockerignore
├── templates/
│   └── index.html       # Single page app (provisioning, dashboard, employee admin)
└── static/               # (kosong, semua CSS/JS inline di index.html)
```

## Catatan Keamanan

- Password user yang di-generate **tidak disimpan** di database tracking —
  hanya ditampilkan sekali di screen saat provisioning. Kalau DBA lupa
  mencatat, generate ulang (buat record baru).
- Tidak ada autentikasi ke tools ini — pastikan akses jaringan ke container
  ini dibatasi (firewall/VPN/internal network saja), karena siapa pun yang
  bisa membuka URL bisa membuat script provisioning.
- User database tracking (`app_user`) sebaiknya **hanya** punya privilege ke
  2 tabel yang dipakai (`access_tracking`, `employee_master`), bukan akses
  penuh ke seluruh database server.
