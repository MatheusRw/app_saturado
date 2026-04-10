"""
Script de diagnóstico para Google Places API
Testa autenticação, geocodificação e busca de estabelecimentos
"""
import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Configurações
API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
PLACES_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

async def testar_chave_api():
    """Testa se a chave da API é válida e tem permissões"""
    print("\n" + "="*60)
    print("1. TESTANDO CHAVE DA API")
    print("="*60)
    
    if not API_KEY:
        print("❌ GOOGLE_PLACES_API_KEY não encontrada no .env")
        return False
    
    print(f"✅ Chave encontrada: {API_KEY[:10]}...{API_KEY[-4:]}")
    
    # Teste simples: geocode de um endereço conhecido
    params = {"address": "Praça Floriano, Rio de Janeiro", "key": API_KEY}
    
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GEOCODE_URL, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "OK":
                print("✅ Chave válida - geocodificação funcionou")
                return True
            else:
                print(f"❌ Chave inválida ou sem permissão: {data.get('status')}")
                return False
        else:
            print(f"❌ Erro HTTP {resp.status_code}")
            return False

async def testar_geocodificacao(municipio: str):
    """Testa geocodificação de um município"""
    print("\n" + "="*60)
    print(f"2. TESTANDO GEOCODIFICAÇÃO: {municipio}")
    print("="*60)
    
    params = {"address": f"{municipio}, Brasil", "key": API_KEY, "language": "pt-BR"}
    
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GEOCODE_URL, params=params)
        print(f"Status HTTP: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"Status API: {data.get('status')}")
            
            if data.get("status") == "OK":
                results = data.get("results", [])
                if results:
                    loc = results[0]["geometry"]["location"]
                    lat, lng = loc["lat"], loc["lng"]
                    endereco_formatado = results[0].get("formatted_address", "")
                    print(f"✅ Coordenadas: {lat}, {lng}")
                    print(f"📌 Endereço: {endereco_formatado}")
                    return lat, lng
                else:
                    print("❌ Nenhum resultado encontrado")
                    return None
            else:
                print(f"❌ Erro na geocodificação: {data.get('status')}")
                return None
        else:
            print(f"❌ Erro HTTP: {resp.status_code}")
            return None

async def testar_text_search(nicho: str, municipio: str, lat: float, lng: float, raio_km: int):
    """Testa Text Search do Google Places"""
    print("\n" + "="*60)
    print(f"3. TESTANDO TEXT SEARCH: '{nicho}' em {municipio}")
    print("="*60)
    
    raio_metros = raio_km * 1000
    field_mask = "places.displayName,places.formattedAddress,places.location,places.businessStatus,places.rating,places.userRatingCount"
    
    body = {
        "textQuery": f"{nicho} em {municipio}",
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": raio_metros,
            }
        },
        "maxResultCount": 10,
        "languageCode": "pt-BR",
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": field_mask,
    }
    
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(PLACES_TEXT_URL, json=body, headers=headers)
        print(f"Status HTTP: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            places = data.get("places", [])
            print(f"✅ Encontrados: {len(places)} lugares")
            
            # Mostra os primeiros resultados
            for i, place in enumerate(places[:5], 1):
                nome = place.get("displayName", {}).get("text", "Sem nome")
                endereco = place.get("formattedAddress", "Sem endereço")
                status = place.get("businessStatus", "Desconhecido")
                rating = place.get("rating", "N/A")
                print(f"\n  {i}. {nome}")
                print(f"     📍 {endereco[:60]}")
                print(f"     🟢 Status: {status} | ⭐ Rating: {rating}")
            
            return places
        else:
            print(f"❌ Erro: {resp.status_code}")
            print(f"Resposta: {resp.text[:500]}")
            return []

async def testar_nearby_search(nicho: str, lat: float, lng: float, raio_km: int):
    """Testa Nearby Search do Google Places"""
    print("\n" + "="*60)
    print(f"4. TESTANDO NEARBY SEARCH: '{nicho}'")
    print("="*60)
    
    # Mapeamento de nicho para tipo Google
    tipo_map = {
        "barbearia": "barber_shop",
        "restaurante": "restaurant",
        "academia": "gym",
        "farmacia": "pharmacy",
        "pet shop": "pet_store",
    }
    tipo = tipo_map.get(nicho.lower(), nicho.lower())
    
    raio_metros = raio_km * 1000
    field_mask = "places.displayName,places.formattedAddress,places.location,places.businessStatus,places.rating"
    
    body = {
        "includedTypes": [tipo],
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": raio_metros,
            }
        },
        "languageCode": "pt-BR",
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": field_mask,
    }
    
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(PLACES_NEARBY_URL, json=body, headers=headers)
        print(f"Status HTTP: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            places = data.get("places", [])
            print(f"✅ Encontrados: {len(places)} lugares")
            
            for i, place in enumerate(places[:5], 1):
                nome = place.get("displayName", {}).get("text", "Sem nome")
                endereco = place.get("formattedAddress", "Sem endereço")
                print(f"\n  {i}. {nome}")
                print(f"     📍 {endereco[:60]}")
            
            return places
        else:
            print(f"❌ Erro: {resp.status_code}")
            print(f"Resposta: {resp.text[:500]}")
            return []

async def testar_com_termos_diferentes(nicho: str, municipio: str, lat: float, lng: float, raio_km: int):
    """Testa diferentes variações do termo de busca"""
    print("\n" + "="*60)
    print(f"5. TESTANDO VARIAÇÕES DO TERMO: '{nicho}'")
    print("="*60)
    
    variacoes = [
        nicho,
        f"{nicho}",
        f"{nicho} perto de mim",
        f"melhor {nicho}",
    ]
    
    field_mask = "places.displayName,places.formattedAddress"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": field_mask,
    }
    
    async with httpx.AsyncClient(timeout=15) as client:
        for variacao in variacoes:
            body = {
                "textQuery": f"{variacao} em {municipio}",
                "locationBias": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": 5000,
                    }
                },
                "maxResultCount": 5,
            }
            
            resp = await client.post(PLACES_TEXT_URL, json=body, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                qtd = len(data.get("places", []))
                print(f"🔍 '{variacao}' → {qtd} resultados")
            else:
                print(f"🔍 '{variacao}' → erro {resp.status_code}")

async def main():
    print("\n" + "🔍"*30)
    print("DIAGNÓSTICO DA API DO GOOGLE PLACES")
    print("🔍"*30)
    
    # 1. Testar chave
    if not await testar_chave_api():
        print("\n❌ Abortando: chave da API inválida ou não configurada")
        print("\nSoluções:")
        print("  1. Verifique se GOOGLE_PLACES_API_KEY está no arquivo .env")
        print("  2. Ative a 'Places API (New)' no Google Cloud Console")
        print("  3. Verifique se a chave tem permissão para a API")
        return
    
    # Configurações do teste
    municipio = input("\n📌 Digite o município para teste (ex: Niterói): ").strip() or "Niterói"
    nicho = input("✂️ Digite o nicho para teste (ex: barbearia): ").strip() or "barbearia"
    raio_km = int(input("📏 Raio em km (padrão 3): ").strip() or "3")
    
    # 2. Geocodificar
    coords = await testar_geocodificacao(municipio)
    if not coords:
        print("\n❌ Abortando: não foi possível geocodificar o município")
        return
    
    lat, lng = coords
    
    # 3. Testar Text Search
    lugares_text = await testar_text_search(nicho, municipio, lat, lng, raio_km)
    
    # 4. Testar Nearby Search (se Text Search falhou)
    if not lugares_text:
        print("\n⚠️ Text Search não retornou resultados. Tentando Nearby Search...")
        await testar_nearby_search(nicho, lat, lng, raio_km)
    
    # 5. Testar variações do termo
    await testar_com_termos_diferentes(nicho, municipio, lat, lng, raio_km)
    
    # 6. Resumo final
    print("\n" + "="*60)
    print("RESUMO DO DIAGNÓSTICO")
    print("="*60)
    
    if lugares_text:
        print(f"✅ SUCESSO! A API retornou {len(lugares_text)} estabelecimentos.")
        print("\n👉 O backend está funcionando. O problema pode ser:")
        print("   - Frontend não está exibindo corretamente")
        print("   - Dados não estão sendo passados para o modelo Relatorio")
    else:
        print("❌ A API NÃO retornou estabelecimentos. Possíveis causas:")
        print("\n   1. Chave da API com permissões insuficientes")
        print("   2. Nenhum estabelecimento encontrado para este nicho/cidade")
        print("   3. Erro na formatação da requisição")
        print("   4. Quota da API excedida")
        print("\n👉 Tente:")
        print("   - Usar um termo mais genérico como 'salão' ao invés de 'barbearia'")
        print("   - Aumentar o raio de busca")
        print("   - Verificar no Google Maps se existem estabelecimentos do tipo")

if __name__ == "__main__":
    asyncio.run(main())