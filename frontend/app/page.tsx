"use client";
import { useState, useEffect, useCallback } from "react";
import { recommend, type Mode, type RecommendVenue } from "@/lib/api";
import Map from "@/components/Map";
import ModeSelector from "@/components/ModeSelector";
import Filters from "@/components/Filters";
import VenueDetailPanel from "@/components/VenueDetailPanel";

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
  const [selectedVenueId, setSelectedVenueId] = useState<string | null>(null);

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
      setSelectedVenueId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load recommendations");
      setVenues([]);
    } finally {
      setLoading(false);
    }
  }, [mode, debouncedRadius, openNow, price]);

  useEffect(() => {
    loadRecommend();
  }, [loadRecommend]);

  const handleVenueSelect = useCallback((venue: RecommendVenue) => {
    setSelectedVenueId((prev) => (prev === venue.id ? null : venue.id));
  }, []);

  const selectedVenue = venues.find((v) => v.id === selectedVenueId) ?? null;
  const selectedRank = selectedVenue ? venues.indexOf(selectedVenue) + 1 : 0;

  return (
    <div className="flex min-h-screen justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-6xl flex-col px-4 py-6 sm:px-8 bg-white dark:bg-black">
        <h1 className="text-3xl font-semibold text-black dark:text-zinc-50">
          ModeMap
        </h1>

        {/* Mode selector */}
        <ModeSelector mode={mode} onModeChange={setMode} />

        {/* Filters */}
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

        {/* Loading / error */}
        {loading && (
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        )}
        {error && (
          <p className="mt-2 text-sm text-red-600">{error}</p>
        )}

        {/* Map + List: side-by-side on md+, stacked on mobile */}
        <div className="mt-4 flex w-full flex-col gap-4 md:flex-row">
          {/* Map */}
          <div className="h-[400px] w-full md:h-[calc(100vh-220px)] md:w-1/2 md:sticky md:top-4 rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-700">
            <Map
              className="w-full h-full"
              venues={venues}
              selectedVenueId={selectedVenueId}
              onMarkerClick={handleVenueSelect}
            />
          </div>

          {/* Right column: detail panel or venue list */}
          <div className="w-full md:w-1/2 md:max-h-[calc(100vh-220px)] md:overflow-y-auto md:pr-1">
            {selectedVenue ? (
              <VenueDetailPanel
                venue={selectedVenue}
                rank={selectedRank}
                onClose={() => setSelectedVenueId(null)}
              />
            ) : (
              <>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  {venues.length} venues found
                </p>
                <ul className="mt-2 space-y-2">
                  {venues.map((venue, index) => (
                    <li
                      key={venue.id}
                      onClick={() => handleVenueSelect(venue)}
                      className="rounded-lg border border-zinc-200 p-3 cursor-pointer transition-colors hover:border-zinc-400 dark:border-zinc-700 dark:hover:border-zinc-500 text-black dark:text-white"
                    >
                      <div className="flex items-baseline gap-2">
                        <span className="text-xs font-semibold text-zinc-400 min-w-[1.5rem]">
                          {index + 1}.
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{venue.name}</div>
                          <div className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
                            {venue.rating !== null && <span>⭐ {venue.rating}</span>}
                            {venue.price_level !== null && (
                              <span className="ml-2">{"$".repeat(venue.price_level)}</span>
                            )}
                            {venue.categories.length > 0 && (
                              <span className="ml-2">{venue.categories.slice(0, 2).join(", ")}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
