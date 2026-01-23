const API_URL = process.env.NEXT_PUBLIC_API_URL;

export interface Venue {
    id: string;
    provider_id: string;
    provider_name: string;
    name: string;
    categories: string[];
    lat: number;
    lng: number;
    address: string | null;
    rating: number | null;
    price_level: number | null;
    hours: Record<string, unknown> | null;
    raw_hours: string | null;
    last_seen_at: string;
    created_at: string;
    updated_at: string;
}

export interface VenueResponse {
    status: string;
    count: number;
    venues: Venue[];
}

export interface SearchParams {
    lat: number;
    lng: number;
    radius ?: number; // default 1000
}

export async function searchVenues(params: SearchParams): Promise<Venue[]> {
    const { lat, lng, radius = 1000 } = params;
    const url = new URL(`${API_URL}/test/google-places`);
    url.searchParams.set("lat", lat.toString());
    url.searchParams.set("lng", lng.toString());
    url.searchParams.set("radius", radius.toString());
    
    console.log(url);
    const response = await fetch(url.toString());
    if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`)
    }

    const data: VenueResponse = await response.json();
    return data.venues;
}

export async function healthCheck(): Promise<boolean> {
    try {
        const response = await fetch(`${API_URL}/health`);
        return response.ok;
    } catch {
        return false;
    }
}
