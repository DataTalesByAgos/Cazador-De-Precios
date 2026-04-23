"""
carrefour.py
------------
Extractor para Carrefour Argentina.
Intenta obtener datos vía API primero; si falla, cae a Selenium.
Campos extraídos: producto, precio, presentacion, supermercado, fuente
"""

import os
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


SUPERMERCADO = "carrefour"

# ---------------------------------------------------------------------------
# 1. Intento por API
# ---------------------------------------------------------------------------
def _extract_via_api() -> list[dict] | None:
    """
    Consulta la API pública de Carrefour (VTEX) con paginación.
    Retorna lista de productos o None si falla completamente.
    """
    products = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Extraer hasta 5 páginas de 50 productos (250 productos)
    for page in range(5):
        _from = page * 50
        _to = _from + 49
        url = (
            "https://www.carrefour.com.ar/api/catalog_system/pub/products/search"
            f"?_from={_from}&_to={_to}"
        )

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            items = resp.json()
            if not items:
                break  # Fin de los resultados
        except Exception as e:
            print(f"    [API] Error en página {page}: {e}")
            break

        for item in items:
            nombre = item.get("productName", "").strip()
            # Buscar precio en el primer SKU disponible
            try:
                sku = item["items"][0]
                precio = str(sku["sellers"][0]["commertialOffer"]["Price"])
                # Presentacion: viene en el campo measurementUnit + unitMultiplier
                measure     = sku.get("measurementUnit", "")
                multiplier  = sku.get("unitMultiplier", 1)
                presentacion = f"{multiplier} {measure}".strip() if measure else ""
            except (IndexError, KeyError):
                continue
            
            # Extraer categoria
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

    return products if products else None


# ---------------------------------------------------------------------------
# 2. Fallback Selenium
# ---------------------------------------------------------------------------
def _build_driver() -> webdriver.Chrome:
    """Construye el driver usando chromium del sistema (Docker) o local."""
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")

    # En Docker: usa el chromium instalado vía apt
    chrome_bin = os.getenv("CHROME_BIN")
    chromedriver = os.getenv("CHROMEDRIVER_PATH")

    if chrome_bin:
        opts.binary_location = chrome_bin

    if chromedriver:
        service = Service(executable_path=chromedriver)
        return webdriver.Chrome(service=service, options=opts)

    # En local: usa el Chrome del sistema (sin service explícito)
    return webdriver.Chrome(options=opts)


def _extract_via_selenium() -> list[dict]:
    """
    Scraping con Chrome headless como fallback.
    """
    driver = _build_driver()
    products = []

    try:
        driver.get("https://www.carrefour.com.ar/bebidas")

        # Esperar a que aparezcan los productos (máx 15s)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CLASS_NAME, "vtex-product-summary-2-x-productBrand")
            )
        )

        items = driver.find_elements(
            By.CLASS_NAME, "vtex-product-summary-2-x-productBrand"
        )

        for item in items[:10]:
            nombre = item.text.strip()
            if not nombre:
                continue

            # Precio
            try:
                price_elem = item.find_element(
                    By.XPATH,
                    "../../..//span[contains(@class,'sellingPrice')]"
                    "|../../..//span[contains(@class,'price')]"
                )
                precio = price_elem.text.strip()
            except Exception:
                precio = ""

            # Presentación (suele estar en el nombre o en un span de descripción)
            try:
                pres_elem = item.find_element(
                    By.XPATH,
                    "../../..//span[contains(@class,'measurementUnit')]"
                    "|../../..//span[contains(@class,'unitMultiplier')]"
                )
                presentacion = pres_elem.text.strip()
            except Exception:
                # Fallback: intentar parsear del nombre del producto
                # ej: "Coca Cola 1.5 L" → presentacion vacío, parse_units lo infiere del nombre
                presentacion = ""

            if not precio:
                continue

            products.append({
                "producto":     nombre,
                "precio":       precio,
                "presentacion": presentacion,
                "supermercado": SUPERMERCADO,
                "fuente":       "selenium",
            })

    finally:
        driver.quit()

    return products


# ---------------------------------------------------------------------------
# 3. Interfaz pública: API primero, Selenium como fallback
# ---------------------------------------------------------------------------
def extract_carrefour() -> list[dict]:
    print("    Intentando API...")
    data = _extract_via_api()

    if data:
        print(f"    API OK → {len(data)} productos")
        return data

    print("    Fallback a Selenium...")
    data = _extract_via_selenium()
    print(f"    Selenium OK → {len(data)} productos")
    return data