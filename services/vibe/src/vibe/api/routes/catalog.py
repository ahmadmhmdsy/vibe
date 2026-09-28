from fastapi import APIRouter
from vibe.providers.catalog import ProviderCatalog

router = APIRouter()

@router.get("/catalog")
async def catalog():
    return [p.__dict__ for p in ProviderCatalog().list_providers()]
