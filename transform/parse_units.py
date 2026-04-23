"""
parse_units.py
--------------
Parsea el texto de presentación de un producto y devuelve:
  - unit_quantity   : cantidad numérica (ej: 500, 1.5, 300)
  - unit_type       : tipo de unidad normalizado ('g', 'ml', 'kg', 'l', 'un')
  - unit_multiplier : cantidad de unidades en un pack (ej: 6 para '6 x 300 ml')
  - base_quantity   : cantidad total en unidad base (g o ml)
  - unit_label      : etiqueta legible para BI (ej: 'por 100g', 'por 100ml')

Formatos soportados:
  '500 g'         → 500g
  '1.5 L'         → 1500ml
  '1 kg'          → 1000g
  '6 x 300 ml'    → 1800ml  (pack)
  '200 g aprox'   → 200g
  '250ml'         → 250ml
  'Un'            → 1 unidad
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Normalización de tipos de unidad
# ---------------------------------------------------------------------------
UNIT_ALIASES: dict[str, str] = {
    # peso
    "g": "g", "gr": "g", "grs": "g", "gramos": "g", "gramo": "g",
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg",
    # volumen
    "ml": "ml", "cc": "ml",
    "l": "l", "lt": "l", "lts": "l", "litro": "l", "litros": "l",
    # unidades
    "un": "un", "u": "un", "und": "un", "unid": "un", "unidad": "un",
    "unidades": "un",
}

# Factores de conversión → unidad base (g o ml)
TO_BASE: dict[str, float] = {
    "g": 1.0,
    "kg": 1000.0,
    "ml": 1.0,
    "l": 1000.0,
    "un": 1.0,   # unidades no se convierten
}

# ---------------------------------------------------------------------------
# Regex principal
# ---------------------------------------------------------------------------
# Cubre: '6 x 300 ml', '500g', '1.5 L', '200 gr aprox'
_PATTERN = re.compile(
    r"""
    (?:(\d+)\s*[xX]\s*)?          # grupo 1: multiplicador de pack (opcional), ej: '6 x'
    (\d+(?:[.,]\d+)?)             # grupo 2: cantidad numérica, ej: '500' o '1.5'
    \s*
    ([a-zA-Z]+)                   # grupo 3: unidad, ej: 'g', 'ml', 'L'
    """,
    re.VERBOSE,
)


def _normalize_number(raw: str) -> float:
    """Convierte '1.500' o '1,5' a float correctamente (formato argentino)."""
    # Si tiene coma como separador decimal: '1,5' → '1.5'
    # Si tiene punto como miles: '1.500' → '1500' (si no hay coma después)
    if "," in raw:
        return float(raw.replace(".", "").replace(",", "."))
    return float(raw)


def parse_presentation(text: Optional[str]) -> dict:
    """
    Recibe el texto crudo de presentación y retorna un dict con todos
    los campos normalizados listos para insertar en dim_product.

    Args:
        text: ej. '6 x 300 ml', '500 g', '1.5 L', None

    Returns:
        {
            'presentacion_raw': str | None,
            'unit_quantity':    float | None,
            'unit_type':        str | None,   # 'g' | 'kg' | 'ml' | 'l' | 'un'
            'unit_multiplier':  int,
            'base_quantity':    float | None, # en g o ml
            'unit_label':       str | None,   # 'por 100g' | 'por 100ml' | 'por unidad'
        }
    """
    result = {
        "presentacion_raw": text,
        "unit_quantity":    None,
        "unit_type":        None,
        "unit_multiplier":  1,
        "base_quantity":    None,
        "unit_label":       None,
    }

    if not text:
        return result

    match = _PATTERN.search(text.strip().lower())
    if not match:
        return result

    raw_mult, raw_qty, raw_unit = match.groups()

    # Multiplicador de pack
    multiplier = int(raw_mult) if raw_mult else 1

    # Cantidad
    try:
        quantity = _normalize_number(raw_qty)
    except ValueError:
        return result

    # Tipo de unidad
    unit_clean = raw_unit.lower().rstrip(".")
    unit_type = UNIT_ALIASES.get(unit_clean)
    if unit_type is None:
        return result  # unidad desconocida → dejar nulo

    # Cantidad base total
    base_quantity = quantity * multiplier * TO_BASE[unit_type]

    # Etiqueta BI
    if unit_type in ("g", "kg"):
        unit_label = "por 100g"
    elif unit_type in ("ml", "l"):
        unit_label = "por 100ml"
    else:
        unit_label = "por unidad"

    result.update({
        "unit_quantity":   quantity,
        "unit_type":       unit_type,
        "unit_multiplier": multiplier,
        "base_quantity":   base_quantity,
        "unit_label":      unit_label,
    })
    return result


# ---------------------------------------------------------------------------
# Cálculo de precio por unidad base (para fact_prices)
# ---------------------------------------------------------------------------
def calc_price_per_unit(price: float, base_quantity: Optional[float],
                        unit_type: Optional[str]) -> Optional[float]:
    """
    Calcula el precio por cada 100g / 100ml / 1 unidad.

    Args:
        price:         precio total del producto
        base_quantity: cantidad base total en g o ml
        unit_type:     'g' | 'kg' | 'ml' | 'l' | 'un'

    Returns:
        precio por unidad base, o None si no se puede calcular
    """
    if not base_quantity or not unit_type or base_quantity <= 0:
        return None

    if unit_type == "un":
        return round(price / base_quantity, 4)

    # Para peso y volumen → precio por 100 unidades base
    return round((price / base_quantity) * 100, 4)
