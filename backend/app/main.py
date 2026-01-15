"""FastAPI application main module."""

from fastapi import FastAPI, HTTPException

app = FastAPI(title="ModeMap API")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/hello")
def hello():
    """Hello endpoint."""
    return {"message": "hello"}


@app.get("/test/google-places")
async def test_google_places(lat: float = 37.7749, lng: float = -122.4194, radius: int = 1000):
    """Test endpoint for Google Places API integration.

    Args:
        lat: Latitude (default: San Francisco)
        lng: Longitude (default: San Francisco)
        radius: Search radius in meters (default: 1000)

    Returns:
        List of nearby venues
    """
    try:
        from app.providers import GooglePlacesClient

        client = GooglePlacesClient()
        venues = await client.search_nearby(
            lat=lat,
            lng=lng,
            radius_m=radius,
            max_results=10,
        )

        return {
            "status": "success",
            "count": len(venues),
            "venues": [venue.model_dump() for venue in venues],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching places: {str(e)}") from e
