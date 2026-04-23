import os
import time
from datetime import date
import mysql.connector
from transform.parse_units import parse_presentation, calc_price_per_unit


# ---------------------------------------------------------------------------
# Conexión con retry
# ---------------------------------------------------------------------------
def get_connection(retries: int = 6, delay: float = 5.0):
    """Intenta conectar a MySQL con reintentos (cubre el gap post-healthcheck)."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return mysql.connector.connect(
                host=os.getenv("DB_HOST", "localhost"),
                user=os.getenv("DB_USER", "root"),
                password=os.getenv("DB_PASSWORD", ""),
                database=os.getenv("DB_NAME", "prices"),
            )
        except mysql.connector.Error as e:
            last_err = e
            print(f"    [DB] Intento {attempt}/{retries} fallido, reintentando en {delay}s...")
            time.sleep(delay)
    raise last_err



# ---------------------------------------------------------------------------
# 1. LOAD BATCH & RAW
# ---------------------------------------------------------------------------
def insert_ingestion_batch(batch_id: str, source_user: str = 'system') -> int:
    """Inserta en dim_ingestion y retorna la ingestion_key."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO dim_ingestion (batch_id, source_user) VALUES (%s, %s)",
        (batch_id, source_user)
    )
    ingestion_key = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return ingestion_key

def insert_raw(data: list[dict], ingestion_key: int) -> list[int]:
    """
    Inserta los registros tal como llegan en raw_prices.
    Retorna los IDs insertados para mantener trazabilidad.
    """
    conn = get_connection()
    cursor = conn.cursor()
    raw_ids = []

    for row in data:
        cursor.execute(
            """
            INSERT INTO raw_prices (ingestion_key, producto, precio, presentacion, supermercado, fuente)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                ingestion_key,
                row["producto"],
                row["precio"],
                row.get("presentacion", ""),
                row["supermercado"],
                row.get("fuente", "selenium"),
            ),
        )
        raw_ids.append(cursor.lastrowid)

    conn.commit()
    cursor.close()
    conn.close()
    return raw_ids


# ---------------------------------------------------------------------------
# 2. HELPERS: upsert de dimensiones
# ---------------------------------------------------------------------------
def _upsert_product(cursor, nombre: str, categoria: str, parsed: dict) -> int:
    """Inserta o actualiza dim_product. Retorna product_id."""
    cursor.execute(
        """
        INSERT INTO dim_product
            (nombre, categoria, unit_quantity, unit_type, unit_multiplier,
             base_quantity, presentacion_raw)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            categoria        = COALESCE(VALUES(categoria), categoria),
            unit_quantity    = VALUES(unit_quantity),
            unit_type        = VALUES(unit_type),
            unit_multiplier  = VALUES(unit_multiplier),
            base_quantity    = VALUES(base_quantity),
            presentacion_raw = VALUES(presentacion_raw)
        """,
        (
            nombre,
            categoria,
            parsed["unit_quantity"],
            parsed["unit_type"],
            parsed["unit_multiplier"],
            parsed["base_quantity"],
            parsed["presentacion_raw"],
        ),
    )
    # Recuperar ID (INSERT o ya existente)
    cursor.execute("SELECT product_id FROM dim_product WHERE nombre = %s", (nombre,))
    return cursor.fetchone()[0]


def _upsert_supermarket(cursor, nombre: str) -> int:
    """Inserta o recupera dim_supermarket. Retorna supermarket_id."""
    cursor.execute(
        "INSERT IGNORE INTO dim_supermarket (nombre) VALUES (%s)", (nombre,)
    )
    cursor.execute(
        "SELECT supermarket_id FROM dim_supermarket WHERE nombre = %s", (nombre,)
    )
    return cursor.fetchone()[0]


def _upsert_date(cursor, d: date) -> int:
    """Inserta o recupera dim_date. Retorna date_id (YYYYMMDD)."""
    date_id = int(d.strftime("%Y%m%d"))
    dia_semana = d.strftime("%A")  # Monday, Tuesday...
    es_finde = d.weekday() >= 5    # Sábado=5, Domingo=6

    cursor.execute(
        """
        INSERT IGNORE INTO dim_date (date_id, fecha, anio, mes, dia, dia_semana, es_finde)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (date_id, d, d.year, d.month, d.day, dia_semana, es_finde),
    )
    return date_id


def _get_source_id(cursor, fuente: str) -> int:
    """Recupera source_id de dim_source."""
    fuente_norm = fuente.lower() if fuente.lower() in ("api", "selenium") else "selenium"
    cursor.execute(
        "SELECT source_id FROM dim_source WHERE nombre = %s", (fuente_norm,)
    )
    row = cursor.fetchone()
    return row[0] if row else 2  # default: selenium


# ---------------------------------------------------------------------------
# 3. LOAD DIMENSIONAL
# ---------------------------------------------------------------------------
def insert_dimensional(data: list[dict], raw_ids: list[int], ingestion_key: int) -> None:
    """
    Transforma y carga en dim_* + fact_prices delegando cálculo a MySQL.

    Args:
        data:          lista de dicts del extractor
        raw_ids:       IDs de raw_prices correspondientes
        ingestion_key: Clave del lote
    """
    conn = get_connection()
    cursor = conn.cursor()
    today = date.today()

    date_id = _upsert_date(cursor, today)

    for row, raw_id in zip(data, raw_ids):
        # --- Limpiar precio ---
        precio_str = row["precio"]
        try:
            precio_float = float(
                precio_str
                .replace("$", "")
                .replace(".", "")
                .replace(",", ".")
                .strip()
            )
        except ValueError:
            print(f"    [WARN] Precio inválido ignorado: {precio_str!r}")
            continue

        if precio_float <= 0:
            print(f"    [WARN] Precio <= 0 ignorado: {precio_float}")
            continue

        # --- Parsear presentación ---
        parsed = parse_presentation(row.get("presentacion") or "")

        # Si la presentación no vino, intentar inferirla del nombre
        if parsed["unit_type"] is None:
            parsed = parse_presentation(row["producto"])

        # --- Upsert dimensiones ---
        product_id     = _upsert_product(cursor, row["producto"], row.get("categoria"), parsed)
        supermarket_id = _upsert_supermarket(cursor, row["supermercado"])
        source_id      = _get_source_id(cursor, row.get("fuente", "selenium"))

        base_qty = parsed["base_quantity"]
        unit_type = parsed["unit_type"]
        unit_label = parsed["unit_label"]

        # Determinamos el multiplicador para el precio_por_unidad
        # Como base_quantity siempre está en gramos o mililitros,
        # multiplicamos por 100 para peso y volumen.
        multiplier_for_price = 100 if unit_type in ('g', 'ml', 'kg', 'l') else 1

        # --- Insertar hecho (Cálculo delegado a DB) ---
        cursor.execute(
            """
            INSERT INTO fact_prices
                (ingestion_key, product_id, supermarket_id, date_id, source_id,
                 price, price_per_unit, unit_label, raw_id)
            VALUES (%s, %s, %s, %s, %s, %s, (%s / NULLIF(%s, 0)) * %s, %s, %s)
            """,
            (
                ingestion_key,
                product_id,
                supermarket_id,
                date_id,
                source_id,
                precio_float,
                precio_float,          # param 1 for division
                base_qty,              # param 2 for NULLIF
                multiplier_for_price,  # param 3 multiplier
                unit_label,
                raw_id,
            ),
        )

    conn.commit()
    cursor.close()
    conn.close()