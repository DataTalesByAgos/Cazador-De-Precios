from dotenv import load_dotenv
load_dotenv()

from extract.carrefour import extract_carrefour
from extract.dia import extract_dia
from extract.coto import extract_coto
from transform.validate import validate, log_rejected
from load.load_db import insert_raw, insert_dimensional


import time

def run_pipeline():
    from datetime import datetime
    
    print("=" * 50)
    print("▶  PIPELINE SUPERMERCADOS")
    print("=" * 50)

    # ── 0. INGESTION BATCH ──────────────────────────────
    batch_id = f"batch_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}"
    print(f"\n[0/4] Iniciar Lote: {batch_id}")
    from load.load_db import insert_ingestion_batch
    ingestion_key = insert_ingestion_batch(batch_id)

    # ── 1. EXTRACT ──────────────────────────────────────
    print("\n[1/4] Extract")
    raw_carrefour = extract_carrefour() or []
    raw_dia = extract_dia() or []
    raw_coto = extract_coto() or []
    
    raw_data = raw_carrefour + raw_dia + raw_coto
    
    if not raw_data:
        print("      ⚠  Fallo la extracción en todas las fuentes. Abortando.")
        return
        
    print(f"      {len(raw_data)} registros extraídos")

    # ── 2. VALIDATE ─────────────────────────────────────
    print("\n[2/4] Validate")
    valid_data, rejected = validate(raw_data)
    log_rejected(rejected)
    print(f"      {len(valid_data)} válidos / {len(rejected)} rechazados")

    if not valid_data:
        print("      ⚠  Sin datos válidos. Pipeline detenido.")
        return

    # ── 3. LOAD RAW ─────────────────────────────────────
    print("\n[3/4] Load RAW")
    raw_ids = insert_raw(valid_data, ingestion_key)
    print(f"      {len(raw_ids)} filas insertadas en raw_prices")

    # ── 4. TRANSFORM + LOAD DIMENSIONAL ─────────────────
    print("\n[4/4] Transform → Load Dimensional")
    insert_dimensional(valid_data, raw_ids, ingestion_key)
    print("      dim_product / dim_supermarket / dim_date / fact_prices actualizados")

    print("\n✅  Pipeline completado.\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--manual":
        print("🛠️  Modo manual detectado.")
    
    # Se ejecuta de forma directa (one-shot). 
    # El scheduling debe manejarse desde afuera (ej: cron, airflow, task scheduler)
    run_pipeline()