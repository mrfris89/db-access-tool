-- ===========================================================
-- DB Access Provisioning Tool — Schema Tracking Database
-- Jalankan di database: db_access_tracking
-- ===========================================================

CREATE TABLE IF NOT EXISTS access_tracking (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(100) NOT NULL,
    nik             VARCHAR(30)  NOT NULL,
    requester       VARCHAR(150) NOT NULL,
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
);

CREATE TABLE IF NOT EXISTS employee_master (
    nik      VARCHAR(30)  PRIMARY KEY,
    nama     VARCHAR(150) NOT NULL,
    unit     VARCHAR(150) NOT NULL,
    subunit  VARCHAR(150) NOT NULL
);