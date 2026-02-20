"use client";
import { useState, useEffect, useCallback } from "react";
import { Drawer } from "vaul";
import { recommend, type Mode, type RecommendVenue } from "@/lib/api";
import Map from "@/components/Map";
import ModeSelector from "@/components/ModeSelector";
import Filters from "@/components/Filters";
import VenueDetailPanel from "@/components/VenueDetailPanel";
import VenueList from "@/components/VenueList";

const DEFAULT_LAT = 37.7749;
const DEFAULT_LNG = -122.4194;
const DEFAULT_RADIUS = 1000;

const SNAP_POINTS = [0.15, 0.5, 1] as const;
const DEFAULT_SNAP = 0.15;

export default function Home() {
  const [mode, setMode] = useState<Mode>("work");
  const [radius, setRadius] = useState(DEFAULT_RADIUS);
  const [openNow, setOpenNow] = useState(false);
  const [price, setPrice] = useState<number | undefined>(undefined);
  const [venues, setVenues] = useState<RecommendVenue[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedVenueId, setSelectedVenueId] = useState<string | null>(null);
  const [snap, setSnap] = useState<number | string | null>(DEFAULT_SNAP);

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

  const handleVenueSelect = useCallback(
    (venue: RecommendVenue) => {
      setSelectedVenueId((prev) => {
        const next = prev === venue.id ? null : venue.id;
        if (next) setSnap(0.5);
        return next;
      });
    },
    [],
  );

  const selectedVenue = venues.find((v) => v.id === selectedVenueId) ?? null;
  const selectedRank = selectedVenue ? venues.indexOf(selectedVenue) + 1 : 0;

  const rightColumnContent = selectedVenue ? (
    <VenueDetailPanel
      venue={selectedVenue}
      rank={selectedRank}
      onClose={() => setSelectedVenueId(null)}
    />
  ) : (
    <VenueList venues={venues} onVenueSelect={handleVenueSelect} />
  );

  return (
    <div className="flex min-h-screen justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-6xl flex-col px-4 py-6 sm:px-8 bg-white dark:bg-black">
        <h1 className="text-3xl font-semibold text-black dark:text-zinc-50">
          ModeMap
        </h1>

        <ModeSelector mode={mode} onModeChange={setMode} />

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

        {loading && (
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        )}
        {error && (
          <p className="mt-2 text-sm text-red-600">{error}</p>
        )}

        {/* ── Desktop: side-by-side (hidden on mobile) ── */}
        <div className="mt-4 hidden w-full gap-4 md:flex md:flex-row">
          <div className="h-[calc(100vh-220px)] w-1/2 sticky top-4 rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-700">
            <Map
              className="w-full h-full"
              venues={venues}
              selectedVenueId={selectedVenueId}
              onMarkerClick={handleVenueSelect}
            />
          </div>
          <div className="w-1/2 max-h-[calc(100vh-220px)] overflow-y-auto pr-1">
            {rightColumnContent}
          </div>
        </div>

        {/* ── Mobile: full map + bottom sheet (hidden on desktop) ── */}
        <div className="mt-4 md:hidden flex-1 relative">
          <div className="h-[calc(100vh-210px)] w-full rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-700">
            <Map
              className="w-full h-full"
              venues={venues}
              selectedVenueId={selectedVenueId}
              onMarkerClick={handleVenueSelect}
            />
          </div>

          <Drawer.Root
            open
            modal={false}
            snapPoints={SNAP_POINTS as unknown as (number | string)[]}
            activeSnapPoint={snap}
            setActiveSnapPoint={setSnap}
          >
            <Drawer.Portal>
              <Drawer.Content
                aria-describedby={undefined}
                className="fixed inset-x-0 bottom-0 z-30 flex flex-col rounded-t-2xl bg-white dark:bg-zinc-900 border-t border-zinc-200 dark:border-zinc-700 shadow-[0_-4px_24px_rgba(0,0,0,0.12)] md:hidden"
                style={{
                  maxHeight: "96vh",
                }}
              >
                <Drawer.Title className="sr-only">Venue results</Drawer.Title>
                {/* Drag handle */}
                <div className="flex justify-center pt-3 pb-2">
                  <div className="h-1.5 w-10 rounded-full bg-zinc-300 dark:bg-zinc-600" />
                </div>

                {/* Scrollable content */}
                <div className="flex-1 overflow-y-auto overscroll-contain px-4 pb-8">
                  {rightColumnContent}
                </div>
              </Drawer.Content>
            </Drawer.Portal>
          </Drawer.Root>
        </div>
      </main>
    </div>
  );
}
