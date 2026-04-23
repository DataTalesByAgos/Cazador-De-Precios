"""
dia.py
------------
Extractor para Supermercados Dia Argentina.
Usa la API pública de VTEX (similar a Carrefour).
Campos extraídos: producto, precio, presentacion, supermercado, fuente
"""

import requests

SUPERMERCADO = "dia"
QUERIES = ["leche", "arroz", "carne", "pan"]

def extract_dia() -> list[dict]:
    """
    Consulta la API pública de Dia (VTEX) usando términos de búsqueda.
    """
    products = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    print("    [Dia] Intentando API...")
    
    for query in QUERIES:
        for page in range(2): # 2 páginas por query = 100 productos max
            _from = page * 50
            _to = _from + 49
            url = (
                "https://diaonline.supermercadosdia.com.ar/api/catalog_system/pub/products/search"
                f"?ft={query}&_from={_from}&_to={_to}"
            )

            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code not in (200, 206):
                    break
                items = resp.json()
                if not items:
                    break  # Fin de los resultados para este query
            except Exception as e:
                print(f"    [Dia] Error en query '{query}' pág {page}: {e}")
                break

            for item in items:
                nombre = item.get("productName", "").strip()
                try:
                    sku = item["items"][0]
                    precio = str(sku["sellers"][0]["commertialOffer"]["Price"])
                    measure     = sku.get("measurementUnit", "")
                    multiplier  = sku.get("unitMultiplier", 1)
                    presentacion = f"{multiplier} {measure}".strip() if measure else ""
                except (IndexError, KeyError):
                    continue
                
                categoria = ""
                if item.get("categories"):
                    categoria = item["categories"][0].replace("/", " ").strip()
                
                if not nombre or not precio:
                    continue

                products.append({
                    "producto":     nombre,
                    "categoria":    categoria,
                    "precio":       precio,
                    "presentacion": presentacion,
                    "supermercado": SUPERMERCADO,
                    "fuente":       "api",
                })

    print(f"    [Dia] API OK → {len(products)} productos")
    return products
