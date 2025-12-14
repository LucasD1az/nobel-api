# client.py
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
from typing import Optional, Dict, Any, List

from pathlib import Path

# =========================
# Configuración
# =========================

BASE_DIR = Path(__file__).resolve().parent

# Ruta al servidor de la API Nobel (server.py)
API_SERVER_BASE_URL = "http://127.0.0.1:8000"

# Credenciales para Basic Auth en operaciones protegidas
API_AUTH = ("admin", "nobel2025")  # las mismas que configuraste en el server

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Nobel API Client")


# =========================
# Página principal (GET)
# =========================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Muestra el formulario inicial, sin resultados.
    """
    return templates.TemplateResponse(
        "client.html",
        {
            "request": request,
            "endpoint_type": None,
            "query_params": {},
            "api_url": None,
            "api_full_url": None,
            "api_server_base": API_SERVER_BASE_URL,
            "status_code": None,
            "error": None,
            "data": None,
        },
    )


# =========================
# Procesar formulario (POST)
# =========================

@app.post("/query", response_class=HTMLResponse)
async def query_api(
    request: Request,
    endpoint_type: str = Form(...),
    discipline: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    yearto: Optional[str] = Form(None),
):
    """
    Procesa el formulario HTML:
    - Construye la URL al servidor (server.py)
    - Envía el GET a /laureates o /countries con los parámetros dados
    - Muestra la respuesta en la misma página
    """

    # Elegimos el path según la opción seleccionada
    if endpoint_type == "laureates":
        path = "/laureates"
    elif endpoint_type == "countries":
        path = "/countries"
    else:
        path = "/laureates"  # fallback

    # Armamos los parámetros de query, solo si el usuario los completó
    params: Dict[str, Any] = {}
    if discipline:
        params["discipline"] = discipline
    if year:
        try:
            params["year"] = int(year)
        except ValueError:
            # Si el usuario escribe cualquier cosa, se ignora
            pass
    if yearto:
        try:
            params["yearto"] = int(yearto)
        except ValueError:
            pass

    api_url = API_SERVER_BASE_URL + path

    status_code = None
    data = None
    error = None
    api_full_url = None

    try:
        resp = requests.get(api_url, params=params, timeout=10)
        status_code = resp.status_code
        api_full_url = str(resp.url)

        if resp.headers.get("content-type", "").startswith("application/json"):
            data = resp.json()
        else:
            data = {"raw_text": resp.text}
        if resp.status_code != 200:
            error = f"El servidor devolvió status {resp.status_code}"
    except requests.RequestException as e:
        error = f"Error al conectar con el servidor: {e}"

    return templates.TemplateResponse(
        "client.html",
        {
            "request": request,
            "endpoint_type": endpoint_type,
            "query_params": params,
            "api_url": api_url,
            "api_full_url": api_full_url,
            "api_server_base": API_SERVER_BASE_URL,
            "status_code": status_code,
            "error": error,
            "data": data,
        },
    )


# =====================================================
# SECCIÓN ADMIN (POST / PUT / DELETE)
# =====================================================

@app.get("/admin", response_class=HTMLResponse)
async def admin_index(request: Request):
    """
    Página de administración:
    - Crear laureado nuevo
    - Buscar laureados por nombre para actualizar/borrar
    """
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "error": None,
            "created": None,
            "search_results": None,
            "updated": None,
            "deleted": None,
        },
    )


@app.post("/admin/create", response_class=HTMLResponse)
async def admin_create(
    request: Request,
    fullName: str = Form(...),
    gender: str = Form("unknown"),
    birthDate: str = Form(""),
    birthCity: str = Form(""),
    birthCountry: str = Form(""),
    awardYear: int = Form(...),
    category: str = Form(...),
    motivation: str = Form(...),
):
    """
    Llama al servidor: POST /laureates
    para crear un nuevo laureado.
    """
    payload = {
        "fullName": fullName,
        "gender": gender,
        "birthDate": birthDate,
        "birthCity": birthCity,
        "birthCountry": birthCountry,
        "nobelPrizes": [
            {
                "awardYear": awardYear,
                "category": category,
                "motivation": motivation,
            }
        ],
    }

    error = None
    created = None

    try:
        resp = requests.post(
            f"{API_SERVER_BASE_URL}/laureates",
            json=payload,
            auth=API_AUTH,
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            error = f"Error al crear laureado: {resp.status_code} – {resp.text}"
        else:
            data = resp.json()
            created = data.get("laureate")
    except requests.RequestException as e:
        error = f"Error al conectar con el servidor: {e}"

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "error": error,
            "created": created,
            "search_results": None,
            "updated": None,
            "deleted": None,
        },
    )


@app.post("/admin/search", response_class=HTMLResponse)
async def admin_search(
    request: Request,
    search_name: str = Form(...),
):
    """
    Llama al servidor: GET /laureates/search?name=...
    para listar posibles laureados y poder editarlos/borrarlos.
    """
    error = None
    search_results: Optional[List[Dict[str, Any]]] = None

    try:
        resp = requests.get(
            f"{API_SERVER_BASE_URL}/laureates/search",
            params={"name": search_name},
            timeout=10,
        )
        if resp.status_code != 200:
            error = f"Error al buscar laureados: {resp.status_code}"
        else:
            data = resp.json()
            search_results = data.get("results", [])
    except requests.RequestException as e:
        error = f"Error al conectar con el servidor: {e}"

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "error": error,
            "created": None,
            "search_results": search_results,
            "updated": None,
            "deleted": None,
        },
    )


@app.post("/admin/update", response_class=HTMLResponse)
async def admin_update(
    request: Request,
    id: str = Form(...),
    fullName: str = Form(""),
    gender: str = Form(""),
    birthDate: str = Form(""),
    birthCity: str = Form(""),
    birthCountry: str = Form(""),
):
    """
    Llama al servidor: PUT /laureates/{id}
    para actualizar campos básicos del laureado.
    """
    payload: Dict[str, Any] = {}
    if fullName:
        payload["fullName"] = fullName
    if gender:
        payload["gender"] = gender
    if birthDate:
        payload["birthDate"] = birthDate
    if birthCity:
        payload["birthCity"] = birthCity
    if birthCountry:
        payload["birthCountry"] = birthCountry

    error = None
    updated = None

    try:
        resp = requests.put(
            f"{API_SERVER_BASE_URL}/laureates/{id}",
            json=payload,
            auth=API_AUTH,
            timeout=10,
        )
        if resp.status_code != 200:
            error = f"Error al actualizar laureado: {resp.status_code} – {resp.text}"
        else:
            data = resp.json()
            updated = data.get("laureate")
    except requests.RequestException as e:
        error = f"Error al conectar con el servidor: {e}"

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "error": error,
            "created": None,
            "search_results": None,
            "updated": updated,
            "deleted": None,
        },
    )


@app.post("/admin/delete", response_class=HTMLResponse)
async def admin_delete(
    request: Request,
    id: str = Form(...),
):
    """
    Llama al servidor: DELETE /laureates/{id}
    para eliminar un laureado.
    """
    error = None
    deleted = None

    try:
        resp = requests.delete(
            f"{API_SERVER_BASE_URL}/laureates/{id}",
            auth=API_AUTH,
            timeout=10,
        )
        if resp.status_code != 200:
            error = f"Error al borrar laureado: {resp.status_code} – {resp.text}"
        else:
            deleted = resp.json()
    except requests.RequestException as e:
        error = f"Error al conectar con el servidor: {e}"

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "error": error,
            "created": None,
            "search_results": None,
            "updated": None,
            "deleted": deleted,
        },
    )
