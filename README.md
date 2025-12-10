# Nobel Laureates API (TP Redes de Datos)

Proyecto de comunicación **API REST Cliente-Servidor** para la materia Redes de Datos, basado en la base de datos pública de los **Premios Nobel**.

Por ahora el proyecto implementa solamente el **servidor** (`server.py`) usando **FastAPI**, y trabaja con un archivo local `data/laureates.json` que contiene la información de los laureados.

---

## Estructura del proyecto

```text
nobel-api/
  server.py        # Servidor FastAPI con endpoints de consulta
  data/
    laureates.json # Datos de laureados (Si no existe, se descarga la primera vez que se inicializa el servidor)
  .gitignore       # Ignora data/, __pycache__/ y otros
```

El archivo `data/laureates.json` no se versiona en git (está en `.gitignore`). Si no existe, el propio servidor lo descarga automáticamente desde la API oficial de Nobel.

## Dependencias

Python 3.10+ (recomendado)

Librerías Python:
* fastapi
* uvicorn
* requests

## Instalación rápida:

```bash
pip install fastapi uvicorn requests
```

## Cómo levantar el servidor
Desde la carpeta del proyecto (donde está server.py):
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Al iniciar, el servidor:

1. Se asegura de que exista la carpeta `data/`.
2. Si no existe `data/laureates.json`, lo descarga de:
```text
https://api.nobelprize.org/2.1/laureates?offset=0&limit=1025
```
3. Carga el contenido de `laureates.json` en memoria (`LAUREATES_DATA`).

## Endpoints implementados hasta ahora
### `GET /`

Endpoint simple de prueba. Devuelve un JSON con:
* Mensaje de OK del servidor
* Si existe o no el archivo `laureates.json`
* Ruta al archivo
* Cantidad de laureados cargados en memoria

Ejemplo de respuesta:

```json
{
  "message": "Servidor Nobel Laureates API OK",
  "data_file_exists": true,
  "data_file": "...\\data\\laureates.json",
  "laureates_loaded": 1018
}
```

### `GET /laureates`

Devuelve los laureados agrupados por año y disciplina, con filtros opcionales.

#### Parámetros:
* `discipline` (opcional, string):
Nombre de la disciplina en inglés (category.en), por ejemplo:
  * "Physics"
  * "Chemistry"
  * "Peace"

Si se omite, se incluyen todas las disciplinas.

* `year` (opcional, int):
Año inicial o año único.

* `yearto` (opcional, int):
Año final.

#### Lógica de filtrado por años:
`year` y `yearto` presentes: premios entre `year` y `yearto` (inclusive).
Solo `year`: premios en ese año.
Solo `yearto`: premios hasta `yearto` (desde el primer año disponible).
Ninguno de los dos: todos los años.

#### Formato de respuesta
```json
{
  "discipline": "Chemistry",
  "year": 1970,
  "yearto": null,
  "total_count": 1,
  "results": [
    {
      "awardYear": 1970,
      "disciplines": [
        {
          "discipline": "Chemistry",
          "count": 1,
          "laureates": [
            "Luis F. Leloir"
          ]
        }
      ]
    }
  ]
}
```

#### Ejemplos de uso
Todas las disciplinas, todos los años:
```text
GET /laureates
```

Solo Física, todos los años:
```text
GET /laureates?discipline=Physics
```

Física entre 1970 y 1980:
```text
GET /laureates?discipline=Physics&year=1970&yearto=1980
```

Todas las disciplinas solo en 2004:
```text
GET /laureates?year=2004
```
