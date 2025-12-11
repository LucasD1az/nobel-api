# client.py
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
from typing import Optional, Dict, Any

from pathlib import Path

# =========================
# Configuración
# =========================

BASE_DIR = Path(__file__).resolve().parent

# Ruta al servidor de la API Nobel
# Cambiá esto a la IP real del servidor cuando lo tengas en otro host.
API_SERVER_BASE_URL = "http://127.0.0.1:8000"

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
    endpoint_type: str = Form(...),       # "laureates" o "countries"
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

    try:
        resp = requests.get(api_url, params=params, timeout=10)
        status_code = resp.status_code
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
            "status_code": status_code,
            "error": error,
            "data": data,
        },
    )
