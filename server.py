# server.py
from fastapi import FastAPI
import requests
import json
from pathlib import Path
from typing import Optional, List, Dict, Deque
from collections import deque
from datetime import datetime, timedelta
import secrets

import io
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import geopandas as gpd
from matplotlib import colors
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials


# =========================
# Configuración de paths y URL
# =========================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LAUREATES_FILE = DATA_DIR / "laureates.json"

NOBEL_API_URL = "https://api.nobelprize.org/2.1/laureates?offset=0&limit=1025"

# Mapeo manual de nombres de países del JSON de Nobel a Natural Earth
COUNTRY_NAME_MAPPING = {
    "USA": "United States of America",
    "the Netherlands": "Netherlands",
    "Russian Empire": "Russia",
    "Prussia": "Germany",
    "Russian Federation": "Russia",
    "Austria-Hungary": "Austria", 
    "Scotland": "United Kingdom", 
    "USSR": "Russia",
    "British Mandate of Palestine": "Palestine",
    "Northern Ireland": "United Kingdom",
    "West Germany": "Germany",
    "Austrian Empire": "Austria",
    "French Algeria": "Algeria",
    "East Timor": "Timor-Leste",
}

app = FastAPI(title="Nobel API Server")

LAUREATES_DATA: List[Dict] = []

# =========================
# Función init_data
# =========================

def get_en(d, default=None):
    """
    Helper: si d es un dict con clave 'en', devuelve d['en'].
    Si es string, lo devuelve tal cual. Si no, default.
    """
    if isinstance(d, dict):
        return d.get("en") or default
    if isinstance(d, str):
        return d
    return default

def simplify_laureate(raw: dict) -> dict:
    """
    Toma un laureado en el formato COMPLEJO de la API Nobel
    y devuelve un dict con solo los campos que nos interesan.

    Soporta tanto:
    - Personas (fullName / knownName + birth)
    - Organizaciones (orgName + founded) -> usamos founded como si fuera birth
    """

    # --- ID ---
    lid = str(raw.get("id"))

    # --- Nombre completo ---
    # Orden de prioridad:
    #  1) fullName.en
    #  2) knownName.en
    #  3) orgName.en  (organizaciones)
    #  4) nativeName  (organizaciones, fallback)
    #  5) "Nombre desconocido"
    full_name = get_en(raw.get("fullName"))
    if not full_name:
        full_name = get_en(raw.get("knownName"))
    if not full_name:
        full_name = get_en(raw.get("orgName"))
    if not full_name:
        full_name = raw.get("nativeName") or "Nombre desconocido"

    # --- Género (para orgs suele faltar, dejamos 'unknown' por defecto) ---
    gender = raw.get("gender", "unknown")

    # --- Nacimiento / Fundación ---
    # Personas: field "birth"
    # Organizaciones: field "founded"
    birth_or_founded = raw.get("birth") or raw.get("founded") or {}
    birth_date = birth_or_founded.get("date")

    place = birth_or_founded.get("place") or {}
    birth_city = get_en(place.get("city"))
    birth_country = get_en(place.get("country"))

    # --- Premios Nobel (lista simplificada) ---
    prizes_out = []
    for prize in raw.get("nobelPrizes", []):
        # awardYear -> int (si se puede)
        award_year_raw = prize.get("awardYear")
        try:
            award_year = int(award_year_raw) if award_year_raw is not None else None
        except ValueError:
            award_year = None

        category = get_en(prize.get("category"))
        motivation = get_en(prize.get("motivation"))

        prizes_out.append(
            {
                "awardYear": award_year,
                "category": category,
                "motivation": motivation,
            }
        )

    return {
        "id": lid,
        "fullName": full_name,
        "gender": gender,
        "birthDate": birth_date,      # para orgs: fecha de fundación
        "birthCity": birth_city,      # para orgs: ciudad de fundación
        "birthCountry": birth_country,  # para orgs: país de fundación
        "nobelPrizes": prizes_out,
    }

def init_data() -> None:
    """
    Se asegura de que exista data/laureates.json.
    - Si el archivo ya existe, NO lo toca.
    - Si no existe, lo descarga desde la API de Nobel, lo simplifica y lo guarda.
    """
    DATA_DIR.mkdir(exist_ok=True)

    if LAUREATES_FILE.exists():
        print(f"[Inicializando] Ya existe {LAUREATES_FILE}, no se descarga nada.")
        return

    print(f"[Inicializando] No se encontró {LAUREATES_FILE}. Descargando desde la API...")
    try:
        resp = requests.get(NOBEL_API_URL, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[Inicializando] Error al descargar datos de Nobel: {e}")
        return

    raw_data = resp.json()
    raw_laureates = raw_data.get("laureates", [])

    simplified_laureates = [simplify_laureate(l) for l in raw_laureates]

    data_to_save = {"laureates": simplified_laureates}

    try:
        with LAUREATES_FILE.open("w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        print(
            f"[Inicializando] Datos simplificados guardados en {LAUREATES_FILE} "
            f"({len(simplified_laureates)} laureados)."
        )
    except OSError as e:
        print(f"[Inicializando] Error al guardar {LAUREATES_FILE}: {e}")


def load_laureates_into_memory() -> None:
    """
    Carga el contenido de laureates.json en LAUREATES_DATA.
    Espera un JSON con clave raíz "laureates": [..., {...}] en formato simplificado.
    """
    global LAUREATES_DATA

    if not LAUREATES_FILE.exists():
        print(f"[load_laureates] No existe {LAUREATES_FILE}. LAUREATES_DATA quedará vacío.")
        LAUREATES_DATA = []
        return

    try:
        with LAUREATES_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[load_laureates] Error al leer {LAUREATES_FILE}: {e}")
        LAUREATES_DATA = []
        return

    LAUREATES_DATA = data.get("laureates", [])
    print(f"[load_laureates] Cargados {len(LAUREATES_DATA)} laureados en memoria.")

def save_laureates_to_file():
    """
    Sobrescribe data/laureates.json con el contenido actual de LAUREATES_DATA.
    """
    with LAUREATES_FILE.open("w", encoding="utf-8") as f:
        json.dump({"laureates": LAUREATES_DATA}, f, ensure_ascii=False, indent=2)

def compute_country_counts(
    discipline: Optional[str] = None,
    year: Optional[int] = None,
    yearto: Optional[int] = None,
) -> Dict[str, int]:
    """
    Devuelve un diccionario {country_name_en: count} usando LAUREATES_DATA
    """

    discipline_lower = discipline.lower() if discipline is not None else None

    country_counts: Dict[str, int] = {}

    for laureate in LAUREATES_DATA:
        country_name_en = laureate.get("birthCountry") or "Unknown"

        nobel_prizes = laureate.get("nobelPrizes", [])

        for prize in nobel_prizes:
            # Filtrar por disciplina si corresponde
            if discipline_lower is not None:
                cat = prize.get("category")
                if not cat or cat.lower() != discipline_lower:
                    continue

            # Año del premio (ya viene como int en el JSON simplificado)
            award_year = prize.get("awardYear")
            if award_year is None:
                continue

            # Lógica de rango de años
            in_range = False
            if year is not None and yearto is not None:
                in_range = year <= award_year <= yearto
            elif year is not None and yearto is None:
                in_range = (award_year == year)
            elif year is None and yearto is not None:
                in_range = (award_year <= yearto)
            else:
                in_range = True

            if not in_range:
                continue

            # Contabilizar el laureado para ese país (por premio)
            country_counts[country_name_en] = country_counts.get(country_name_en, 0) + 1

    return country_counts

def _get_next_laureate_id() -> str:
    """
    Genera un nuevo id numérico como string, tomando el máximo id actual + 1.
    """
    max_id = 0
    for laureate in LAUREATES_DATA:
        try:
            cur = int(laureate.get("id", 0))
            if cur > max_id:
                max_id = cur
        except (TypeError, ValueError):
            continue
    return str(max_id + 1)

def _find_laureate_index_by_id(laureate_id: str) -> Optional[int]:
    """
    Devuelve el índice en LAUREATES_DATA del laureado con ese id, o None si no existe.
    """
    for idx, laureate in enumerate(LAUREATES_DATA):
        if str(laureate.get("id")) == str(laureate_id):
            return idx
    return None

# -------------------------------------------------------------------
# AUTENTICACIÓN BASIC PARA POST / PUT / DELETE
# -------------------------------------------------------------------

security = HTTPBasic()

# Base de usuarios simulada (para el TP alcanza así).
USUARIOS: Dict[str, str] = {
    "admin": "nobel2025",
}


def verificar_credenciales(
    credenciales: HTTPBasicCredentials = Depends(security),
) -> str:
    """
    Valida usuario/contraseña enviados por el cliente usando Basic Auth.

    - El navegador / cliente arma el header:
      Authorization: Basic base64("usuario:password")
    - FastAPI lo decodifica y nos da `credenciales.username` y `credenciales.password`.
    - Comparamos contra nuestro diccionario USUARIOS.
    """
    pwd_correcta = USUARIOS.get(credenciales.username)

    if not pwd_correcta or not secrets.compare_digest(
        credenciales.password, pwd_correcta
    ):
        # 401 + cabecera WWW-Authenticate para que el cliente sepa que tiene que mandar credenciales.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credenciales.username

# -------------------------------------------------------------------
# RATE LIMITING: límite de solicitudes por segundo para métodos que modifican datos
# -------------------------------------------------------------------

VENTANA = timedelta(seconds=1)   # ventana de tiempo
MAX_PETICIONES = 5              # por IP, por segundo (ajustá si querés)

cubos_ip: Dict[str, Deque[datetime]] = {}


@app.middleware("http")
async def limitador(request: Request, call_next):
    """
    Middleware de rate limiting:
    - Solo limita métodos de escritura: POST, PUT, DELETE.
    - Máximo MAX_WRITE_REQUESTS por segundo y por IP.
    """
    metodo = request.method.upper()

    # Solo aplicamos límite a métodos "peligrosos"
    if metodo in ("POST", "PUT", "DELETE"):
        ip = request.client.host
        ahora = datetime.utcnow()

        cubo = cubos_ip.setdefault(ip, deque())

        # Limpiamos timestamps fuera de la ventana
        while cubo and (ahora - cubo[0]) > VENTANA:
            cubo.popleft()

        # Si se excede el límite, devolvemos 429 *sin* lanzar excepción
        if len(cubo) >= MAX_PETICIONES:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": (
                        "Demasiadas solicitudes de modificación: "
                        f"máximo {MAX_PETICIONES} req/s"
                    )
                },
            )

        # Registramos esta nueva solicitud
        cubo.append(ahora)

    # Si no se supera el límite, continuamos normal
    response = await call_next(request)
    return response

@app.on_event("startup")
def on_startup():
    """
    Se ejecuta automáticamente cuando arranca el servidor.
    - Garantiza que exista laureates.json.
    - Carga los laureados en memoria.
    """
    init_data()
    load_laureates_into_memory()


# =========================
# Endpoint mínimo de prueba
# =========================

@app.get("/")
def read_root():
    """
    Endpoint mínimo para verificar que el servidor está vivo.
    """
    return {
        "message": "Servidor Nobel Laureates API OK",
        "data_file_exists": LAUREATES_FILE.exists(),
        "data_file": str(LAUREATES_FILE),
        "laureates_loaded": len(LAUREATES_DATA),
    }

# =========================
# GET: filtrar por disciplina y años
# =========================

@app.get("/laureates")
def get_laureates(
    discipline: Optional[str] = None,
    year: Optional[int] = None,
    yearto: Optional[int] = None,
):
    """
    Devuelve los laureados agrupados por año y disciplina, con filtros opcionales.

    - discipline (opcional): si se especifica, filtra por categoría (string exacto),
      ej. "Physics", "Chemistry", "Peace", "Economic Sciences", etc.
      Si se omite, incluye todas las disciplinas.

    - year / yearto: mismo comportamiento que en /countries.
   """

    discipline_lower = discipline.lower() if discipline is not None else None

    # year_groups[awardYear][discipline] = [fullName1, fullName2, ...]
    year_groups: Dict[int, Dict[str, List[str]]] = {}

    for laureate in LAUREATES_DATA:
        full_name = laureate.get("fullName") or "Nombre desconocido"
        nobel_prizes = laureate.get("nobelPrizes", [])

        for prize in nobel_prizes:
            # Categoría simple (string)
            cat = prize.get("category")
            if not cat:
                continue

            cat_en = cat  # ya es string en inglés en el JSON simplificado

            # Filtro de disciplina si corresponde
            if discipline_lower is not None and cat_en.lower() != discipline_lower:
                continue

            # Año del premio (int)
            award_year = prize.get("awardYear")
            if award_year is None:
                continue

            # Lógica de rango de años
            in_range = False
            if year is not None and yearto is not None:
                in_range = year <= award_year <= yearto
            elif year is not None and yearto is None:
                in_range = (award_year == year)
            elif year is None and yearto is not None:
                in_range = (award_year <= yearto)
            else:
                in_range = True

            if not in_range:
                continue

            # Agregamos al grupo de ese año y disciplina
            year_disciplines = year_groups.setdefault(award_year, {})
            laureates_list = year_disciplines.setdefault(cat_en, [])
            laureates_list.append(full_name)

    # Construimos la respuesta ordenada por año
    results_list = []
    total_count = 0

    for award_year in sorted(year_groups.keys()):
        disciplines_dict = year_groups[award_year]

        disciplines_list = []
        for disc_name in sorted(disciplines_dict.keys()):
            names = disciplines_dict[disc_name]
            count = len(names)
            total_count += count

            disciplines_list.append({
                "discipline": disc_name,
                "count": count,
                "laureates": names,
            })

        results_list.append({
            "awardYear": award_year,
            "disciplines": disciplines_list,
        })

    return {
        "discipline": discipline,
        "year": year,
        "yearto": yearto,
        "total_count": total_count,
        "results": results_list,
    }


@app.get("/countries")
def get_countries(
    discipline: Optional[str] = None,
    year: Optional[int] = None,
    yearto: Optional[int] = None,
):
    """
    Devuelve la cantidad de laureados por país, con filtros opcionales.
    """

    country_counts = compute_country_counts(discipline, year, yearto)
    total_count = sum(country_counts.values())

    # Ordenar por cantidad descendente
    sorted_items = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)

    results_list = [
        {"country": country, "count": count}
        for country, count in sorted_items
    ]

    return {
        "discipline": discipline,
        "year": year,
        "yearto": yearto,
        "total_count": total_count,
        "results": results_list,
    }


@app.get("/countries-map")
def get_countries_map(
    discipline: Optional[str] = None,
    year: Optional[int] = None,
    yearto: Optional[int] = None,
):
    """
    Devuelve un mapa mundial (choropleth) en formato PNG, coloreando los países
    según la cantidad de laureados, usando la misma lógica de filtros que /countries.

    - La escala de colores es logarítmica (para distinguir bien países con pocos Nobel).
    - Países con 0 laureados se muestran en gris.
    """

    country_counts = compute_country_counts(discipline, year, yearto)

    if not country_counts:
        raise HTTPException(status_code=404, detail="No hay datos para esos filtros")

    # Pasamos counts a DataFrame
    df_counts = pd.DataFrame(
        [{"country": c, "count": n} for c, n in country_counts.items()]
    )

    # Normalizamos nombres de países según el mapping
    df_counts["country_normalized"] = df_counts["country"].apply(
        lambda c: COUNTRY_NAME_MAPPING.get(c, c)
    )

    # Cargamos mapa mundial desde el dataset de GeoPandas
    world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))

    # Hacemos merge por nombre
    merged = world.merge(
        df_counts,
        how="left",
        left_on="name",
        right_on="country_normalized",
    )

    # 'count' puede tener NaN (no hay Nobel) → los convertimos a 0 para stats
    merged["count"] = merged["count"].fillna(0)

    # Columna para ploteo: los 0 los ponemos como NaN para que se dibujen con el color de "missing"
    merged["count_plot"] = merged["count"].replace(0, np.nan)

    # Definimos normalizador logarítmico solo si hay algún valor > 0
    max_count = merged["count"].max()
    if max_count <= 0:
        raise HTTPException(
            status_code=500,
            detail="No se pudieron calcular valores positivos para el mapa.",
        )

    norm = colors.LogNorm(vmin=1, vmax=max_count)

    # Dibujamos el mapa
    fig, ax = plt.subplots(1, 1, figsize=(12, 6))
    merged.plot(
        column="count_plot",
        ax=ax,
        legend=True,
        cmap="OrRd",
        norm=norm,
        linewidth=0.4,
        edgecolor="black",
        missing_kwds={
            "color": "lightgrey",
            "edgecolor": "black",
            #"hatch": "///",
        },
    )
    ax.set_axis_off()

    title_parts = ["Premios Nobel por país"]
    if discipline:
        title_parts.append(f"– {discipline}")
    if year and yearto:
        title_parts.append(f"({year}–{yearto})")
    elif year and not yearto:
        title_parts.append(f"({year})")
    elif yearto and not year:
        title_parts.append(f"(hasta {yearto})")
    ax.set_title(" ".join(title_parts))

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")

@app.get("/laureates/search")
def search_laureates(name: str):
    """
    Búsqueda simple por nombre (match parcial, case-insensitive).
    Sirve para que el cliente encuentre un laureado antes de editar/borrar.

    Ejemplo:
      GET /laureates/search?name=einstein
    """
    name_lower = name.lower()
    results = []

    for laureate in LAUREATES_DATA:
        full_name = laureate.get("fullName", "")
        if name_lower in full_name.lower():
            results.append(laureate)

    return {
        "query": name,
        "count": len(results),
        "results": results,
    }

@app.post("/laureates")
def create_laureate(
    payload: dict,
    usuario: str = Depends(verificar_credenciales),
):
    """
    Crea un nuevo laureado.

    Campos esperados en `payload`:
    - fullName (str)
    - gender (str)
    - birthDate (str, ej. "1970-01-01")
    - birthCity (str)
    - birthCountry (str)
    - nobelPrizes: lista de objetos con:
        * awardYear (int o str convertible a int)
        * category (str, ej. "Physics")
        * motivation (str)
    """

    required_fields = ["fullName", "gender", "birthDate", "birthCity", "birthCountry", "nobelPrizes"]
    for field in required_fields:
        if field not in payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Falta el campo obligatorio '{field}'",
            )

    # Validamos y normalizamos los premios
    cleaned_prizes = []
    if not isinstance(payload["nobelPrizes"], list) or len(payload["nobelPrizes"]) == 0:
        raise HTTPException(status_code=400, detail="nobelPrizes debe ser una lista no vacía")

    for prize in payload["nobelPrizes"]:
        if not isinstance(prize, dict):
            raise HTTPException(status_code=400, detail="Cada premio debe ser un objeto JSON")

        try:
            year = int(prize["awardYear"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Cada premio debe tener 'awardYear' numérico")

        category = prize.get("category")
        motivation = prize.get("motivation")
        if not category or not motivation:
            raise HTTPException(
                status_code=400,
                detail="Cada premio debe tener 'category' y 'motivation'",
            )

        cleaned_prizes.append(
            {
                "awardYear": year,
                "category": str(category),
                "motivation": str(motivation),
            }
        )

    nuevo_laureado = {
        "id": _get_next_laureate_id(),
        "fullName": str(payload["fullName"]),
        "gender": str(payload["gender"]),
        "birthDate": str(payload["birthDate"]),
        "birthCity": str(payload["birthCity"]),
        "birthCountry": str(payload["birthCountry"]),
        "nobelPrizes": cleaned_prizes,
    }

    LAUREATES_DATA.append(nuevo_laureado)
    save_laureates_to_file()

    return {
        "msg": f"Laureado creado por {usuario}",
        "laureate": nuevo_laureado,
    }

@app.put("/laureates/{laureate_id}")
def update_laureate(
    laureate_id: str,
    payload: dict,
    usuario: str = Depends(verificar_credenciales),
):
    """
    Actualiza un laureado existente. Se puede mandar un subconjunto de campos.
    Si viene `nobelPrizes`, se reemplaza la lista completa por la nueva.
    """

    idx = _find_laureate_index_by_id(laureate_id)
    if idx is None:
        raise HTTPException(status_code=404, detail="Laureado no encontrado")

    laureate = LAUREATES_DATA[idx]

    # Campos simples
    for field in ["fullName", "gender", "birthDate", "birthCity", "birthCountry"]:
        if field in payload and payload[field] is not None:
            laureate[field] = str(payload[field])

    # Si nos mandan nueva lista de premios, la validamos igual que en el POST
    if "nobelPrizes" in payload and payload["nobelPrizes"] is not None:
        if not isinstance(payload["nobelPrizes"], list) or len(payload["nobelPrizes"]) == 0:
            raise HTTPException(status_code=400, detail="nobelPrizes debe ser una lista no vacía")

        cleaned_prizes = []
        for prize in payload["nobelPrizes"]:
            if not isinstance(prize, dict):
                raise HTTPException(status_code=400, detail="Cada premio debe ser un objeto JSON")

            try:
                year = int(prize["awardYear"])
            except (KeyError, ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Cada premio debe tener 'awardYear' numérico")

            category = prize.get("category")
            motivation = prize.get("motivation")
            if not category or not motivation:
                raise HTTPException(
                    status_code=400,
                    detail="Cada premio debe tener 'category' y 'motivation'",
                )

            cleaned_prizes.append(
                {
                    "awardYear": year,
                    "category": str(category),
                    "motivation": str(motivation),
                }
            )

        laureate["nobelPrizes"] = cleaned_prizes

    LAUREATES_DATA[idx] = laureate
    save_laureates_to_file()

    return {
        "msg": f"Laureado actualizado por {usuario}",
        "laureate": laureate,
    }

@app.delete("/laureates/{laureate_id}")
def delete_laureate(
    laureate_id: str,
    usuario: str = Depends(verificar_credenciales),
):
    """
    Elimina un laureado por id.
    """

    idx = _find_laureate_index_by_id(laureate_id)
    if idx is None:
        raise HTTPException(status_code=404, detail="Laureado no encontrado")

    eliminado = LAUREATES_DATA.pop(idx)
    save_laureates_to_file()

    return {
        "msg": f"Laureado eliminado por {usuario}",
        "id": laureate_id,
        "fullName": eliminado.get("fullName"),
    }
