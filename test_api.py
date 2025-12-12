import requests
from pprint import pprint

BASE_URL = "http://127.0.0.1:8000"
AUTH = ("admin", "nobel2025")  # Basic Auth para POST/PUT/DELETE


def test_search():
    print("\n=== GET /laureates/search?name=bohr ===")
    resp = requests.get(f"{BASE_URL}/laureates/search", params={"name": "bohr"})
    print("Status:", resp.status_code)
    pprint(resp.json())


def test_create():
    print("\n=== POST /laureates (crear demo Ada) ===")
    payload = {
        "fullName": "Ada Lovelace (Demo Nobel)",
        "gender": "female",
        "birthDate": "1815-12-10",
        "birthCity": "London",
        "birthCountry": "United Kingdom",
        "nobelPrizes": [
            {
                "awardYear": 2025,
                "category": "Physics",
                "motivation": "For demo purposes in the API TP",
            }
        ],
    }
    resp = requests.post(f"{BASE_URL}/laureates", json=payload, auth=AUTH)
    print("Status:", resp.status_code)
    data = resp.json()
    pprint(data)
    # Devuelvo el id nuevo para usarlo en las siguientes pruebas
    return data.get("laureate", {}).get("id")


def test_update(laureate_id: str):
    print(f"\n=== PUT /laureates/{laureate_id} (cambiar país) ===")
    payload = {
        "birthCountry": "Argentina",
        "nobelPrizes": [
            {
                "awardYear": 2025,
                "category": "Physics",
                "motivation": "For an important contribution to API homework",
            }
        ],
    }
    resp = requests.put(f"{BASE_URL}/laureates/{laureate_id}", json=payload, auth=AUTH)
    print("Status:", resp.status_code)
    pprint(resp.json())


def test_delete(laureate_id: str):
    print(f"\n=== DELETE /laureates/{laureate_id} ===")
    resp = requests.delete(f"{BASE_URL}/laureates/{laureate_id}", auth=AUTH)
    print("Status:", resp.status_code)
    pprint(resp.json())


if __name__ == "__main__":
    # 1) Probar búsqueda
    test_search()

    # 2) Crear un laureado de demo
    new_id = test_create()
    if not new_id:
        print("No se pudo obtener el id del laureado creado, corto acá.")
    else:
        # 3) Actualizarlo
        test_update(new_id)

        # 3b) Actualizarlo muchas veces
        for i in range(15):
            test_update(new_id)

        # 4) Borrarlo
        test_delete(new_id)

        # 5) Ver que ya no aparece en la búsqueda
        print("\n=== Buscar Ada de nuevo ===")
        resp = requests.get(
            f"{BASE_URL}/laureates/search",
            params={"name": "Ada Lovelace (Demo Nobel)"},
        )
        print("Status:", resp.status_code)
        pprint(resp.json())
