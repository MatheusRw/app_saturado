"""
Integração exclusiva com Google Places API (Text Search)
- Busca por texto tipo "barbearia em Niterói"
- Retorna lista completa com nome, endereço, rating, etc.
"""
import httpx
import asyncio
import os
from typing import Any

PLACES_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

FIELD_MASK = (
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.businessStatus,"
    "places.types,"
    "places.rating,"
    "places.userRatingCount,"
    "places.priceLevel"
)

async def geocodificar_municipio(municipio: str, api_key: str) -> tuple[float, float] | None:
    params = {"address": f"{municipio}, Brasil", "key": api_key, "language": "pt-BR"}
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.get(GEOCODE_URL, params=params)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    loc = results[0]["geometry"]["location"]
                    return loc["lat"], loc["lng"]
        except Exception:
            pass
    return None

async def buscar_por_google_places(
    nicho: str,
    municipio: str,
    raio_km: int = 3,
    max_resultados: int = 60,
) -> list[dict[str, Any]]:
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        return []

    coords = await geocodificar_municipio(municipio, api_key)
    if not coords:
        return []

    lat, lng = coords
    raio_metros = raio_km * 1000
    lugares = []
    page_token = None
    pages = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        while pages < 3 and len(lugares) < max_resultados:
            body = {
                "textQuery": f"{nicho} em {municipio}",
                "locationBias": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": raio_metros,
                    }
                },
                "maxResultCount": min(20, max_resultados - len(lugares)),
                "languageCode": "pt-BR",
            }
            if page_token:
                body["pageToken"] = page_token

            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": FIELD_MASK,
            }

            try:
                resp = await client.post(PLACES_TEXT_URL, json=body, headers=headers)
                if resp.status_code != 200:
                    print(f"Erro Google Places: {resp.status_code} - {resp.text[:200]}")
                    break

                data = resp.json()
                items = data.get("places", [])
                for item in items:
                    normalized = _normalizar_lugar(item)
                    if normalized:
                        lugares.append(normalized)

                page_token = data.get("nextPageToken")
                pages += 1
                if not page_token:
                    break
                await asyncio.sleep(0.5)  # respeitar rate limit

            except Exception as e:
                print(f"Exceção na busca: {e}")
                break

    return lugares

def _normalizar_lugar(raw: dict) -> dict | None:
    try:
        nome = raw.get("displayName", {}).get("text", "Sem nome")
        endereco = raw.get("formattedAddress", "")
        partes = [p.strip() for p in endereco.split(",")]
        bairro = partes[1] if len(partes) >= 3 else (partes[0] if partes else "Não informado")
        if any(c.isdigit() for c in bairro) or len(bairro) <= 3:
            bairro = partes[0] if partes else "Não informado"

        loc = raw.get("location", {})
        lat = loc.get("latitude", 0.0)
        lng = loc.get("longitude", 0.0)

        status = raw.get("businessStatus", "OPERATIONAL")
        ativa = status == "OPERATIONAL"

        rating = raw.get("rating")
        num_avaliacoes = raw.get("userRatingCount", 0)

        # Pega o primeiro tipo amigável
        tipos = raw.get("types", [])
        tipo_amigavel = tipos[0] if tipos else "estabelecimento"

        return {
            "nome": nome[:60],
            "endereco": endereco,
            "bairro": bairro,
            "latitude": lat,
            "longitude": lng,
            "ativa": ativa,
            "status": status,
            "rating": rating,
            "num_avaliacoes": num_avaliacoes,
            "tipo": tipo_amigavel,
        }
    except Exception:
        return None

def agregar_dados_places(lugares: list[dict], lat_centro: float = 0, lng_centro: float = 0) -> dict:
    if not lugares:
        return {
            "total_empresas": 0,
            "empresas_ativas": 0,
            "por_bairro": {},
            "rating_medio": None,
            "total_avaliacoes": 0,
            "lat_centro": lat_centro,
            "lng_centro": lng_centro,
            "lista": [],
        }

    ativos = [l for l in lugares if l["ativa"]]

    por_bairro = {}
    for l in lugares:
        b = (l["bairro"] or "Não informado").strip().title()
        por_bairro[b] = por_bairro.get(b, 0) + 1
    por_bairro = dict(sorted(por_bairro.items(), key=lambda x: -x[1])[:8])

    ratings = [l["rating"] for l in lugares if l.get("rating") is not None]
    rating_medio = round(sum(ratings) / len(ratings), 1) if ratings else None
    total_avaliacoes = sum(l.get("num_avaliacoes", 0) for l in lugares)

    return {
        "total_empresas": len(lugares),
        "empresas_ativas": len(ativos),
        "por_bairro": por_bairro,
        "rating_medio": rating_medio,
        "total_avaliacoes": total_avaliacoes,
        "lat_centro": lat_centro,
        "lng_centro": lng_centro,
        "lista": lugares,
    }