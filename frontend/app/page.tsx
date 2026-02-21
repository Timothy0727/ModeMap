"use client";

import { Drawer } from "vaul";
import { useRecommend } from "@/hooks/useRecommend";
import Map from "@/components/Map";
import ModeSelector from "@/components/ModeSelector";
import Filters from "@/components/Filters";
import VenueDetailPanel from "@/components/VenueDetailPanel";
import VenueList from "@/components/VenueList";

const SNAP_POINTS = [0.15, 0.5, 1] as const;

export default function Home() {
  const presenter = useRecommend();

  const rightColumnContent = presenter.selectedVenue ? (
    <VenueDetailPanel
      venue={presenter.selectedVenue}
      rank={presenter.selectedRank}
      onClose={presenter.onCloseDetail}
    />
  ) : (
    <VenueList venues={presenter.venues} onVenueSelect={presenter.onVenueSelect} />
  );

  return (
    <div className="flex min-h-screen justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex w-full max-w-6xl flex-col px-4 py-6 sm:px-8 bg-white dark:bg-black">
        <h1 className="text-3xl font-semibold text-black dark:text-zinc-50">
          ModeMap
        </h1>

        <ModeSelector mode={presenter.mode} onModeChange={presenter.onModeChange} />

        <div className="mt-3 w-full">
          <Filters
            radius={presenter.radius}
            onRadiusChange={presenter.onRadiusChange}
            openNow={presenter.openNow}
            onOpenNowChange={presenter.onOpenNowChange}
            price={presenter.price}
            onPriceChange={presenter.onPriceChange}
          />
        </div>

        {presenter.loading && (
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        )}
        {presenter.error && (
          <p className="mt-2 text-sm text-red-600">{presenter.error}</p>
        )}

        {/* ── Desktop: side-by-side (hidden on mobile) ── */}
        <div className="mt-4 hidden w-full gap-4 md:flex md:flex-row">
          <div className="h-[calc(100vh-220px)] w-1/2 sticky top-4 rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-700">
            <Map
              className="w-full h-full"
              venues={presenter.venues}
              selectedVenueId={presenter.selectedVenueId}
              onMarkerClick={presenter.onVenueSelect}
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
              venues={presenter.venues}
              selectedVenueId={presenter.selectedVenueId}
              onMarkerClick={presenter.onVenueSelect}
            />
          </div>

          <Drawer.Root
            open
            modal={false}
            snapPoints={SNAP_POINTS as unknown as (number | string)[]}
            activeSnapPoint={presenter.snap}
            setActiveSnapPoint={presenter.setSnap}
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
                <div className="flex justify-center pt-3 pb-2">
                  <div className="h-1.5 w-10 rounded-full bg-zinc-300 dark:bg-zinc-600" />
                </div>
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
