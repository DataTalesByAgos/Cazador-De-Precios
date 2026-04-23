"""
coto.py
------------
Extractor para Coto Digital Argentina.
Usa la API pública de Constructor.io.
Campos extraídos: producto, precio, presentacion, supermercado, fuente
"""

import requests

SUPERMERCADO = "coto"
QUERIES = ["leche", "arroz", "carne", "pan"]

def extract_coto() -> list[dict]:
    """
    Consulta la API pública de Coto (Constructor.io) usando términos de búsqueda.
    """
    products = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    print("    [Coto] Intentando API...")
    
    for query in QUERIES:
        url = f"https://ac.cnstrc.com/search/{query}?key=key_r6xzz4IAoTWcipni"

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            items = data.get("response", {}).get("results", [])
        except Exception as e:
            print(f"    [Coto] Error en query '{query}': {e}")
            continue

        for item in items:
            nombre = item.get("value", "").strip()
            
            # Coto manda la info de precios como una lista de precios por sucursal dentro de 'data'
            item_data = item.get("data", {})
            precio = item_data.get("price")
            if not precio or not isinstance(precio, list):
                continue
                
            precio_val = precio[0].get("listPrice") or precio[0].get("formatPrice")
            if not precio_val:
                continue

            precio_str = str(precio_val)
            
            categoria = ""
            groups = item_data.get("groups", [])
            if groups:
                categoria = groups[0].get("display_name", "").strip()
            
            # En Coto la presentación suele estar en el nombre.
            # No tienen unitMultiplier o unitType estructurado aquí, parse_units.py se encargará.
            presentacion = ""

            products.append({
                "producto":     nombre,
                "categoria":    categoria,
                "precio":       precio_str,
                "presentacion": presentacion,
                "supermercado": SUPERMERCADO,
                "fuente":       "api",
            })

    print(f"    [Coto] API OK → {len(products)} productos")
    return products
