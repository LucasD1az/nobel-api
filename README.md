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

## Instalación del proyecto y creación del entorno virtual

Antes de instalar las dependencias, es necesario crear y activar un entorno virtual.  
A continuación se detalla el procedimiento tanto para Linux como para Windows.

### Crear entorno virtual e instalar dependencias en Linux (Ubuntu / Debian)

Instalar `venv`:

```bash
sudo apt install python3-venv -y
python3 -m venv .venv
```

Desde la carpeta del proyecto:

```bash
python3 -m venv .venv
````

Activar el entorno virtual:

```bash
source .venv/bin/activate
```

Instalar dependencias del sistema necesarias para GeoPandas:

```bash
sudo apt install -y gdal-bin libgdal-dev libspatialindex-dev
```

Instalar las dependencias del proyecto:

```bash
pip install -r requirements.txt
```

---

### Crear entorno virtual e instalar dependencias en Windows

Desde la carpeta del proyecto, crear el entorno virtual:

```bash
python -m venv .venv
```

o, según la instalación:

```bash
py -3 -m venv .venv
```

Activar el entorno virtual:

Usando PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

O usando CMD:

```cmd
.venv\Scripts\activate.bat
```

Instalar dependencias desde `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Cómo levantar el servidor
Desde la carpeta del proyecto (donde está server.py) y en la misma terminal en la que activamos nuestro entorno virtual:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000 &

```

Al iniciar, el servidor:

1. Se asegura de que exista la carpeta `data/`.
2. Si no existe `data/laureates.json`, lo descarga de:
```text
https://api.nobelprize.org/2.1/laureates?offset=0&limit=1025
```
3. Carga el contenido de `laureates.json` en memoria (`LAUREATES_DATA`).

## Cómo levantar el cliente
En la misma terminal donde levantamos el servidor:

```bash
uvicorn client:app --host 0.0.0.0 --port 8001 &
```

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

### `GET /countries`

Devuelve la cantidad de laureados por país, con filtros opcionales.

#### Parámetros:
* `discipline` (opcional, string):  
Nombre de la disciplina en inglés (`category.en`), por ejemplo:
  * "Physics"
  * "Chemistry"
  * "Peace"

Si se omite, se incluyen **todas** las disciplinas.

* `year` (opcional, int):  
Año inicial o año único.

* `yearto` (opcional, int):  
Año final.

#### Lógica de filtrado por años:
- `year` y `yearto` presentes: premios entre `year` y `yearto` (inclusive).  
- Solo `year`: premios en ese año.  
- Solo `yearto`: premios hasta `yearto` (desde el primer año disponible).  
- Ninguno de los dos: todos los años.

El país se toma del lugar de nacimiento del laureado: `birth.place.country.en` (si está disponible).  
Si no se encuentra, se usa `"Unknown"`.

#### Formato de respuesta
```json
{
  "discipline": "Physics",
  "year": 1970,
  "yearto": 1972,
  "total_count": 6,
  "results": [
    {
      "country": "USA",
      "count": 3
    },
    {
      "country": "Hungary",
      "count": 1
    },
    {
      "country": "Sweden",
      "count": 1
    },
    {
      "country": "France",
      "count": 1
    }
  ]
}
```

#### Ejemplos de uso

Todas las disciplinas, todos los años:
```text
GET /countries
```

Solo Física, todos los años:
```text
GET /countries?discipline=Physics
```

Química solo en 2004:
```text
GET /countries?discipline=Chemistry&year=2004
```

Todas las disciplinas hasta 1950:
```text
GET /countries?yearto=1950
```

Física entre 1970 y 1980:
```text
GET /countries?discipline=Physics&year=1970&yearto=1980
```
