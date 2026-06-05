BEGIN;

-- 1. Ensure the new aggregate tables exist.
CREATE TABLE IF NOT EXISTS purchase_order_summary (
    id SERIAL PRIMARY KEY,
    supplier_code VARCHAR NOT NULL,
    supplier_name VARCHAR,
    material_code VARCHAR NOT NULL,
    material_name VARCHAR,
    order_count INTEGER DEFAULT 0,
    total_qty DOUBLE PRECISION DEFAULT 0,
    total_amount DOUBLE PRECISION DEFAULT 0,
    avg_price DOUBLE PRECISION DEFAULT 0,
    avg_tax_net_price DOUBLE PRECISION DEFAULT 0,
    latest_price DOUBLE PRECISION,
    latest_tax_net_price DOUBLE PRECISION,
    latest_date TIMESTAMP,
    lowest_price DOUBLE PRECISION,
    lowest_date TIMESTAMP,
    highest_price DOUBLE PRECISION,
    highest_date TIMESTAMP,
    avg_30_days DOUBLE PRECISION DEFAULT 0,
    recent_order_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_purchase_order_summary_supplier_material UNIQUE (supplier_code, material_code)
);

CREATE TABLE IF NOT EXISTS purchase_order_monthly_stats (
    id SERIAL PRIMARY KEY,
    supplier_code VARCHAR NOT NULL,
    supplier_name VARCHAR,
    material_code VARCHAR NOT NULL,
    material_name VARCHAR,
    stat_month TIMESTAMP NOT NULL,
    order_count INTEGER DEFAULT 0,
    total_qty DOUBLE PRECISION DEFAULT 0,
    total_amount DOUBLE PRECISION DEFAULT 0,
    avg_tax_net_price DOUBLE PRECISION DEFAULT 0,
    min_tax_net_price DOUBLE PRECISION,
    max_tax_net_price DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_purchase_order_monthly_supplier_material_month UNIQUE (supplier_code, material_code, stat_month)
);

CREATE INDEX IF NOT EXISTS ix_purchase_order_summary_supplier_code ON purchase_order_summary (supplier_code);
CREATE INDEX IF NOT EXISTS ix_purchase_order_summary_material_code ON purchase_order_summary (material_code);
CREATE INDEX IF NOT EXISTS ix_purchase_order_summary_latest_date ON purchase_order_summary (latest_date);

CREATE INDEX IF NOT EXISTS ix_purchase_order_monthly_stats_supplier_code ON purchase_order_monthly_stats (supplier_code);
CREATE INDEX IF NOT EXISTS ix_purchase_order_monthly_stats_material_code ON purchase_order_monthly_stats (material_code);
CREATE INDEX IF NOT EXISTS ix_purchase_order_monthly_stats_stat_month ON purchase_order_monthly_stats (stat_month);

-- 2. Drop the legacy raw-history table and its related sequence/indexes.
DROP TABLE IF EXISTS purchase_order_history CASCADE;
DROP SEQUENCE IF EXISTS purchase_order_history_id_seq CASCADE;

COMMIT;
