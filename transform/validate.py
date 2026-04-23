"""
validate.py
-----------
Capa de validación mínima del pipeline.
Se ejecuta ANTES de la carga RAW para descartar registros inválidos
y loggear los rechazados sin detener el pipeline.

Reglas:
  - producto no vacío
  - precio > 0 (parseable como número)
  - estructura del dict válida (campos obligatorios presentes)
"""

import re
from typing import Optional


REQUIRED_FIELDS = {"producto", "precio", "supermercado"}

# Precio: acepta '$1.500,50', '1500.50', '1500', etc.
_PRICE_RE = re.compile(r"[\d.,]+")


def _parse_price_safe(raw: str) -> Optional[float]:
    """Intenta convertir el string de precio a float. Retorna None si falla."""
    try:
        cleaned = (
            raw.replace("$", "")
               .replace(".", "")
               .replace(",", ".")
               .strip()
        )
        val = float(cleaned)
        return val if val > 0 else None
    except (ValueError, AttributeError):
        return None


def validate(data: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Valida una lista de registros extraídos.

    Returns:
        (valid, rejected)
        - valid:    registros que pasan todas las reglas (limpios y deduplicados)
        - rejected: registros descartados con campo '__reason' explicando por qué
    """
    valid = []
    rejected = []
    seen = set()

    for row in data:
        reason = _check(row)
        if reason:
            rejected.append({**row, "__reason": reason})
            continue
            
        # 4. Limpieza de strings
        producto_limpio = row["producto"].strip().title()
        super_limpio = row["supermercado"].strip().title()
        
        # Limpiar categoría si existe
        categoria_limpia = str(row.get("categoria", "")).strip().title()
        if categoria_limpia:
            row["categoria"] = categoria_limpia
        else:
            row["categoria"] = None
        
        row["producto"] = producto_limpio
        row["supermercado"] = super_limpio

        # 5. Deduplicación dentro del mismo lote (batch)
        unique_key = (producto_limpio, super_limpio)
        if unique_key in seen:
            rejected.append({**row, "__reason": "duplicado en este lote"})
        else:
            seen.add(unique_key)
            valid.append(row)

    return valid, rejected


def _check(row: dict) -> Optional[str]:
    """Retorna el motivo de rechazo, o None si el registro es válido."""

    # 1. Estructura: campos obligatorios presentes
    missing = REQUIRED_FIELDS - row.keys()
    if missing:
        return f"Campos faltantes: {missing}"

    # 2. Producto no vacío
    producto = str(row.get("producto", "")).strip()
    if not producto:
        return "producto vacío"

    # 3. Precio parseable y > 0
    precio_raw = str(row.get("precio", "")).strip()
    if not precio_raw:
        return "precio vacío"

    if _parse_price_safe(precio_raw) is None:
        return f"precio no parseable o <= 0: {precio_raw!r}"

    return None  # válido


def log_rejected(rejected: list[dict]) -> None:
    """Imprime un resumen de los registros rechazados."""
    if not rejected:
        return
    print(f"    [VALIDATE] {len(rejected)} registro(s) rechazado(s):")
    for r in rejected:
        print(f"      ✗ {r.get('producto', '?')!r} | "
              f"precio={r.get('precio', '?')!r} | "
              f"motivo: {r.get('__reason', '?')}")
