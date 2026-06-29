-- Migration: Add DB Cluster Master table + FK columns to access_tracking
-- Date: 2026-06-29
-- Purpose: Support cluster management feature untuk provisioning

-- 1. Create db_cluster_master table
CREATE TABLE IF NOT EXISTS db_cluster_master (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    rdbms           ENUM('oracle','mysql','postgres') NOT NULL,
    cluster_name    VARCHAR(150) NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_rdbms_cluster (rdbms, cluster_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Add FK columns to access_tracking (safe, additive, backward-compatible)
-- Check if column exists sebelum ALTER untuk safety
ALTER TABLE access_tracking
ADD COLUMN IF NOT EXISTS db_cluster_id INT NULL AFTER db_host;

ALTER TABLE access_tracking
ADD COLUMN IF NOT EXISTS oracle_service_name VARCHAR(150) NULL AFTER db_cluster_id;

-- 3. Add Foreign Key constraint (one-time, safe kalau sudah ada — MySQL akan skip)
-- Block delete jika cluster masih dipakai di tracking (ON DELETE RESTRICT)
ALTER TABLE access_tracking
ADD CONSTRAINT IF NOT EXISTS fk_tracking_cluster
FOREIGN KEY (db_cluster_id) REFERENCES db_cluster_master(id)
ON DELETE RESTRICT;

-- Verifikasi
SELECT '✓ Migration complete' AS status;
SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ('db_cluster_master', 'access_tracking')
ORDER BY TABLE_NAME, ORDINAL_POSITION;
