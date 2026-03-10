export type Mode = "work" | "date" | "quick_bite" | "budget";

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
    
    const response = await fetch(url.toString());
    if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
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

export interface RecommendParams {
    mode: Mode;
    lat: number;
    lng: number;
    radius?: number;
    open_now?: boolean;
    price?: number;
    max_results?: number;
}

export interface RecommendVenue {
    id: string;
    provider_id: string;
    provider_name: string;
    name: string;
    categories: string[];
    lat: number;
    lng: number;
    distance_m: number | null;
    address: string | null;
    rating: number | null;
    price_level: number | null;
    hours: Record<string, unknown> | null;
    raw_hours: string | null;
    explanations: string[] | null;
}

export interface RecommendMeta {
    mode: Mode;
    radius: number;
    total_results: number;
    returned_results: number;
    cache_hit: boolean | null;
    time_taken_ms: number | null;
}

export interface RecommendResponse {
    meta: RecommendMeta;
    venues: RecommendVenue[]
}

export async function recommend(params: RecommendParams): Promise<RecommendResponse> {
    if (!API_URL) {
        throw new Error("API_URL is not defined");
    }

    const url = new URL(`${API_URL}/recommend`);
    url.searchParams.set("mode", params.mode);
    url.searchParams.set("lat", params.lat.toString());
    url.searchParams.set("lng", params.lng.toString());
    if (params.radius !== undefined && params.radius >= 100) {
        url.searchParams.set("radius", params.radius.toString());
    }
    if (params.open_now !== undefined) {
        url.searchParams.set("open_now", params.open_now.toString());
    }
    if (params.price !== undefined) {
        url.searchParams.set("price", params.price.toString());
    }
    if (params.max_results !== undefined) {
        url.searchParams.set("max_results", params.max_results.toString());
    }

    const response = await fetch(url.toString());
    if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data = (await response.json()) as RecommendResponse;

    data.venues = data.venues.map((venue) => ({
        ...venue,
        explanations: venue.explanations ?? null,
    }));

    return data;
}
