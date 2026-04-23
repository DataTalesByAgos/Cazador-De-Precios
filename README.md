# Cazador de Precios (Supermarket Price Pipeline)

![Diagrama de Arquitectura de Cazador de Precios](cazador_precios.png)

Un pipeline de datos ETL (Extracción, Transformación y Carga) robusto y de grado analítico para monitorear precios de supermercados en Argentina (Carrefour, Coto y Día). El sistema extrae datos utilizando APIs nativas, los estandariza, normaliza sus unidades de medida y los carga en una base de datos MySQL estructurada bajo un Modelo en Estrella, dejándolos listos para su visualización en Power BI.

## Características Principales

- **Extracción de Alta Velocidad**: Utiliza las APIs públicas de las plataformas VTEX (Carrefour, Día) y Constructor.io (Coto), evitando el overhead y la lentitud de herramientas basadas en navegación como Selenium.
- **Trazabilidad de Lotes**: Implementa un registro estricto por batches (`dim_ingestion`). Cada ejecución genera un lote único, permitiendo un linaje claro de los datos y facilidad para realizar rollbacks selectivos.
- **Cálculo Analítico Delegado**: La estandarización de métricas críticas, como el cálculo del *Precio por Unidad* (ej. precio por 100g o por 1L), se delega al motor SQL para garantizar la integridad aritmética y evitar divisiones por cero.
- **Arquitectura de Contenedores Efímeros**: Sigue mejores prácticas de infraestructura. El proceso de extracción no permanece activo consumiendo memoria; se ejecuta de forma aislada e instantánea bajo demanda mediante un scheduler externo (Cron / Task Scheduler).

## Estructura de Datos (Modelo en Estrella)

La base de datos MySQL (`prices`) está optimizada para lectura analítica:

- `dim_product`: Catálogo único de productos, con limpieza de nombres, presentación inferida y categorización automática.
- `dim_supermarket`: Entidades de supermercados relevadas.
- `dim_date`: Dimensión de tiempo estandarizada (incluye flags de fines de semana).
- `dim_ingestion`: Metadatos técnicos de cada corrida del pipeline.
- `fact_prices`: Tabla de hechos transaccional que consolida los precios vinculados a sus dimensiones mediante Foreign Keys.

## Requisitos Previos

- Docker y Docker Compose instalados.
- Puerto `3306` (MySQL) y `8080` (phpMyAdmin) libres en el host.

## Configuración y Despliegue

1. **Clonar el repositorio y configurar variables:**
   Asegúrese de contar con un archivo `.env` en la raíz del proyecto:
   ```env
   DB_HOST=mysql
   DB_USER=root
   DB_PASSWORD=supersecret
   DB_NAME=prices

   MYSQL_ROOT_PASSWORD=supersecret
   MYSQL_DATABASE=prices
   ```

2. **Levantar la Infraestructura (Base de Datos):**
   ```bash
   docker compose up -d
   ```
   *Nota: Este comando inicia los servicios de MySQL y phpMyAdmin, pero no ejecuta la extracción automáticamente.*

## Ejecución del Pipeline

La aplicación Python utiliza el perfil `cron` en Docker Compose, garantizando su naturaleza efímera. 

### Ejecución Manual
Para forzar una extracción inmediata y ver los logs en la terminal:
```bash
docker compose run --rm app python main.py --manual
```

### Ejecución Programada (Producción)
Se recomienda delegar la calendarización al sistema operativo anfitrión.

**En Linux (Crontab):**
```cron
# Ejecutar todos los días a las 02:00 AM y 14:00 PM
0 2,14 * * * cd /ruta/al/proyecto && docker compose run --rm app python main.py
```

**En Windows (Task Scheduler):**
Cree una "Tarea Básica" que apunte al comando `docker` con los argumentos `compose run --rm app python main.py`, estableciendo la ruta del proyecto en el campo "Iniciar en".

## Visualización (Power BI)

1. Instale el **MySQL Connector/NET** en su máquina local.
2. Desde Power BI, obtenga datos desde MySQL apuntando a `127.0.0.1:3306` con la base de datos `prices`.
3. Importe las tablas `fact_prices`, `dim_product`, `dim_supermarket` y `dim_date`. El modelo en estrella será detectado automáticamente mediante las claves foráneas, permitiendo el cruce y análisis del "Precio Estandarizado" (`price_per_unit`) de forma transparente.
