"use client";
import { useState, useEffect, useCallback } from "react";
import { recommend, type Mode, type RecommendVenue } from "@/lib/api";
import Map from "@/components/Map";
import ModeSelector from "@/components/ModeSelector";
import Filters from "@/components/Filters";


const DEFAULT_LAT = 37.7749;
const DEFAULT_LNG = -122.4194;
const DEFAULT_RADIUS = 1000;

export default function Home() {
  const [mode, setMode] = useState<Mode>("work");
  const [radius, setRadius] = useState(DEFAULT_RADIUS);
  const [openNow, setOpenNow] = useState(false);
  const [price, setPrice] = useState<number | undefined>(undefined);
  const [venues, setVenues] = useState<RecommendVenue[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounce radius so the API isn't called on every slider pixel
  const [debouncedRadius, setDebouncedRadius] = useState(radius);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedRadius(radius), 300);
    return () => clearTimeout(timer);
  }, [radius]);

  const loadRecommend = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await recommend({
        mode,
        lat: DEFAULT_LAT,
        lng: DEFAULT_LNG,
        radius: debouncedRadius,
        open_now: openNow,
        price,
        max_results: 60,
      });
      setVenues(res.venues);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load recommendations");
      setVenues([]);
    } finally {
      setLoading(false);
    }
  }, [mode, debouncedRadius, openNow, price]);

  // Load recommendations on mount and whenever filters change
  useEffect(() => {
    loadRecommend();
  }, [loadRecommend]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex min-h-screen w-full max-w-3xl flex-col items-center justify-between py-32 px-16 bg-white dark:bg-black sm:items-start">
        <h1 className="text-3xl font-semibold text-black dark:text-zinc-50">
          ModeMap
        </h1>

        {/* Mode selector */}
        <ModeSelector mode={mode} onModeChange={setMode} />

        {/* Filters: radius slider, open now, price */}
        <div className="mt-3 w-full">
          <Filters
            radius={radius}
            onRadiusChange={setRadius}
            openNow={openNow}
            onOpenNowChange={setOpenNow}
            price={price}
            onPriceChange={setPrice}
          />
        </div>

        {/* Loading / error feedback */}
        {loading && (
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        )}
        {error && (
          <p className="mt-2 text-sm text-red-600">{error}</p>
        )}

        {/* Map section */}
        <div className="mt-4 w-full h-[400px]">
          <Map className="w-full h-full" venues={venues} />
        </div>

        {/* Ranked venue list */}
        <div className="mt-4 w-full">
          <p className="text-zinc-600 dark:text-zinc-400">
            Found {venues.length} venues
          </p>
          <ul className="mt-2 space-y-2">
            {venues.map((venue, index) => (
              <li
                key={venue.id}
                className="rounded border p-2 text-black dark:text-white"
              >
                <span className="mr-2 text-zinc-400">{index + 1}.</span>
                {venue.name} — {venue.rating ?? "N/A"} ⭐
                {venue.price_level !== null && (
                  <span className="ml-2 text-zinc-500">
                    {"$".repeat(venue.price_level)}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      </main>
    </div>
  );
}
