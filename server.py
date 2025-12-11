# server.py
from fastapi import FastAPI
import requests
import json
from pathlib import Path
from typing import Optional, List, Dict

import io
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import geopandas as gpd
from matplotlib import colors
from fastapi.responses import StreamingResponse
from fastapi import HTTPException

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

app = FastAPI(title="Nobel Laureates API - Etapa init")

LAUREATES_DATA: List[Dict] = []

# =========================
# Función init_data
# =========================

def init_data() -> None:
    """
    Se asegura de que exista data/laureates.json.
    - Si el archivo ya existe, NO lo toca.
    - Si no existe, lo descarga desde la API de Nobel y lo guarda.
    """
    # Nos aseguramos de que exista la carpeta data/
    DATA_DIR.mkdir(exist_ok=True)

    if LAUREATES_FILE.exists():
        print(f"[Inicializando] Ya existe {LAUREATES_FILE}, no se descarga nada.")
        return

    print(f"[Inicializando] No se encontró {LAUREATES_FILE}. Descargando desde la API...")
    try:
        resp = requests.get(NOBEL_API_URL, timeout=30)
        resp.raise_for_status()  # lanza error si status_code no es 2xx
    except requests.RequestException as e:
        # Si falla, lo mostramos en consola y dejamos que el server arranque igual
        print(f"[Inicializando] Error al descargar datos de Nobel: {e}")
        return

    data = resp.json()

    try:
        with LAUREATES_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[Inicializando] Datos guardados en {LAUREATES_FILE}")
    except OSError as e:
        print(f"[Inicializando] Error al guardar {LAUREATES_FILE}: {e}")

def load_laureates_into_memory() -> None:
    """
    Carga el contenido de laureates.json en la variable global LAUREATES_DATA.
    Espera un JSON con clave raíz "laureates": [..., {...}]
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

def compute_country_counts(
    discipline: Optional[str] = None,
    year: Optional[int] = None,
    yearto: Optional[int] = None,
) -> Dict[str, int]:
    """
    Devuelve un diccionario {country_name_en: count} usando la misma lógica
    de filtros que /countries.
    """
    discipline_lower = discipline.lower() if discipline is not None else None

    country_counts: Dict[str, int] = {}

    for laureate in LAUREATES_DATA:
        # --- Obtener país en inglés del nacimiento ---
        country_name_en = None
        birth = laureate.get("birth")
        if isinstance(birth, dict):
            place = birth.get("place")
            if isinstance(place, dict):
                country = place.get("country")
                # country puede ser dict {"en": "..."} o string
                if isinstance(country, dict):
                    country_name_en = country.get("en")
                elif isinstance(country, str):
                    country_name_en = country

        if not country_name_en:
            country_name_en = "Unknown"

        # --- Iterar los premios Nobel de esta persona ---
        nobel_prizes = laureate.get("nobelPrizes", [])
        for prize in nobel_prizes:
            # Filtrar por disciplina si corresponde
            if discipline_lower is not None:
                cat = prize.get("category")
                if isinstance(cat, dict):
                    cat_en = cat.get("en")
                else:
                    cat_en = cat
                if not cat_en or cat_en.lower() != discipline_lower:
                    continue

            # Año del premio
            award_year_str = prize.get("awardYear")
            try:
                award_year = int(award_year_str) if award_year_str is not None else None
            except ValueError:
                continue

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

            # Contabilizar el laureado para ese país
            country_counts[country_name_en] = country_counts.get(country_name_en, 0) + 1

    return country_counts

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
    Devuelve los laureados agrupados por año y disciplina.

    - discipline opcional:
        * si se especifica, filtra por esa categoría (category.en, case-insensitive)
        * si no se especifica, incluye todas las disciplinas
    - year y yearto (opcionales):
        * ambos presentes  -> premios entre year y yearto (inclusive)
        * solo year        -> premios en ese año
        * solo yearto      -> premios hasta yearto (desde el primer año disponible)
        * ninguno          -> todos los años

    Formato de respuesta:
    {
      "discipline": "Physics" | null,
      "year": ...,
      "yearto": ...,
      "total_count": N,
      "results": [
        {
          "awardYear": 1975,
          "disciplines": [
            {
              "discipline": "Physics",
              "count": 3,
              "laureates": ["Aage Niels Bohr", "...", "..."]
            },
            {
              "discipline": "Chemistry",
              "count": 2,
              "laureates": ["...", "..."]
            }
          ]
        },
        ...
      ]
    }
    """

    discipline_lower = discipline.lower() if discipline is not None else None

    # year_groups[awardYear][discipline] = [fullName1, fullName2, ...]
    year_groups: Dict[int, Dict[str, List[str]]] = {}

    for laureate in LAUREATES_DATA:
        # fullName está como objeto con idiomas, ej. {"en": "A. Michael Spence", ...}
        full_name = None
        if isinstance(laureate.get("fullName"), dict):
            full_name = laureate["fullName"].get("en") or next(
                iter(laureate["fullName"].values()), None
            )
        elif isinstance(laureate.get("knownName"), dict):
            full_name = laureate["knownName"].get("en") or next(
                iter(laureate["knownName"].values()), None
            )

        if full_name is None:
            full_name = "Nombre desconocido"

        nobel_prizes = laureate.get("nobelPrizes", [])

        for prize in nobel_prizes:
            # categoría
            cat = prize.get("category")
            if isinstance(cat, dict):
                cat_en = cat.get("en")
            else:
                cat_en = cat

            if not cat_en:
                continue

            # Si se especificó disciplina, filtramos
            if discipline_lower is not None and cat_en.lower() != discipline_lower:
                continue

            # año del premio
            award_year_str = prize.get("awardYear")
            try:
                award_year = int(award_year_str) if award_year_str is not None else None
            except ValueError:
                continue

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
            year_groups.setdefault(award_year, {})
            year_groups[award_year].setdefault(cat_en, []).append(full_name)

    # Armamos la lista ordenada por año
    results_list = []
    total_count = 0

    for award_year in sorted(year_groups.keys()):
        disciplines_list = []
        # Podés ordenar las disciplinas alfabéticamente si querés
        for disc_name in sorted(year_groups[award_year].keys()):
            laureate_names = year_groups[award_year][disc_name]
            count = len(laureate_names)
            total_count += count
            disciplines_list.append({
                "discipline": disc_name,
                "count": count,
                "laureates": laureate_names,
            })

        results_list.append({
            "awardYear": award_year,
            "disciplines": disciplines_list,
        })

    return {
        "discipline": discipline,  # puede ser None si no se filtró
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
    (Misma lógica que ya tenías, ahora apoyada en compute_country_counts).
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
    # (esto te funciona porque hiciste downgrade de versión)
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
        # Caso borde: todo es 0 (muy raro, pero por las dudas)
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
        missing_kwds={  # para geometrías donde count_plot es NaN
            "color": "lightgrey",
            "edgecolor": "black",
            "hatch": "///",
        },
    )
    ax.set_axis_off()

    # Título prolijo
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