-- ============================================================
-- METADATA LAYER
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_ingestion (
    ingestion_key   INT AUTO_INCREMENT PRIMARY KEY,
    batch_id        VARCHAR(100) NOT NULL UNIQUE,
    load_timestamp  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_user     VARCHAR(50) DEFAULT 'system'
);

-- ============================================================
-- RAW LAYER
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_prices (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    ingestion_key INT         NOT NULL,
    producto      TEXT        NOT NULL,
    precio        TEXT        NOT NULL,
    presentacion  TEXT,                                    -- ej: '500 g', '1.5 L', '6 x 300 ml'
    supermercado  TEXT        NOT NULL,
    fuente        VARCHAR(20) NOT NULL DEFAULT 'selenium', -- 'api' | 'selenium'
    fecha         TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ingestion_key) REFERENCES dim_ingestion(ingestion_key) ON DELETE CASCADE
);

-- ============================================================
-- DIMENSIONAL LAYER
-- ============================================================


-- dim_product
CREATE TABLE IF NOT EXISTS dim_product (
    product_id          INT AUTO_INCREMENT PRIMARY KEY,
    nombre              VARCHAR(255)   NOT NULL UNIQUE,
    categoria           VARCHAR(100),
    -- Unidad de presentación (parseada del texto crudo)
    unit_quantity       DECIMAL(10,3),                   -- ej: 500 / 1.5 / 300
    unit_type           VARCHAR(10),                     -- 'g' | 'kg' | 'ml' | 'l' | 'un'
    unit_multiplier     SMALLINT DEFAULT 1,              -- para '6 x 300 ml' → 6
    -- Normalizado a gramos o mililitros para comparación BI
    base_quantity       DECIMAL(10,3),                   -- unit_quantity * unit_multiplier (en g o ml)
    presentacion_raw    VARCHAR(100),                    -- texto original sin limpiar
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- dim_supermarket
CREATE TABLE IF NOT EXISTS dim_supermarket (
    supermarket_id  INT AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL UNIQUE,
    pais            VARCHAR(50)  DEFAULT 'Argentina'
);

-- dim_date
CREATE TABLE IF NOT EXISTS dim_date (
    date_id     INT PRIMARY KEY,           -- formato YYYYMMDD
    fecha       DATE NOT NULL,
    anio        SMALLINT NOT NULL,
    mes         TINYINT  NOT NULL,
    dia         TINYINT  NOT NULL,
    dia_semana  VARCHAR(15),
    es_finde    BOOLEAN  DEFAULT FALSE
);

-- dim_source
CREATE TABLE IF NOT EXISTS dim_source (
    source_id   INT AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(20) NOT NULL UNIQUE   -- 'api' | 'selenium'
);

INSERT IGNORE INTO dim_source (nombre) VALUES ('api'), ('selenium');

-- fact_prices
CREATE TABLE IF NOT EXISTS fact_prices (
    fact_id              INT AUTO_INCREMENT PRIMARY KEY,
    ingestion_key        INT           NOT NULL,
    product_id           INT           NOT NULL,
    supermarket_id       INT           NOT NULL,
    date_id              INT           NOT NULL,
    source_id            INT           NOT NULL,
    price                DECIMAL(15,2) NOT NULL,
    -- Precio normalizado por unidad base (permite comparar independiente del tamaño)
    price_per_unit       DECIMAL(15,4),                  -- price / base_quantity
    unit_label           VARCHAR(20),                    -- 'por 100g' | 'por 100ml' | 'por unidad'
    raw_id               INT,                            -- trazabilidad hacia raw_prices
    FOREIGN KEY (ingestion_key)  REFERENCES dim_ingestion(ingestion_key) ON DELETE CASCADE,
    FOREIGN KEY (product_id)     REFERENCES dim_product(product_id),
    FOREIGN KEY (supermarket_id) REFERENCES dim_supermarket(supermarket_id),
    FOREIGN KEY (date_id)        REFERENCES dim_date(date_id),
    FOREIGN KEY (source_id)      REFERENCES dim_source(source_id),
    FOREIGN KEY (raw_id)         REFERENCES raw_prices(id)
);