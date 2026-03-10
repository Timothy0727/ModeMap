"use client";

import { type RecommendVenue } from "@/lib/api";

interface VenueListProps {
  venues: RecommendVenue[];
  onVenueSelect: (venue: RecommendVenue) => void;
  openNowFilter?: boolean;
}

function OpenClosedBadge({ hours }: { hours: Record<string, unknown> | null }) {
  if (!hours || hours.open_now === undefined) return null;
  const isOpen = Boolean(hours.open_now);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-xs font-medium ${
        isOpen
          ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400"
          : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400"
      }`}
    >
      <span className={`h-1 w-1 rounded-full ${isOpen ? "bg-green-500" : "bg-red-500"}`} />
      {isOpen ? "Open" : "Closed"}
    </span>
  );
}

export default function VenueList({ venues, onVenueSelect, openNowFilter }: VenueListProps) {
  const formatDistance = (distance_m: number | null): string | null => {
    if (distance_m == null) return null;
    if (distance_m < 1000) {
      return `${Math.round(distance_m)} m`;
    }
    return `${(distance_m / 1000).toFixed(1)} km`;
  };

  return (
    <>
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        {venues.length} venues found
        {openNowFilter && (
          <span className="ml-1.5 text-zinc-600 dark:text-zinc-300">(open now only)</span>
        )}
      </p>
      <ul className="mt-2 space-y-2">
        {venues.map((venue, index) => (
          <li
            key={venue.id}
            onClick={() => onVenueSelect(venue)}
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
                  {formatDistance(venue.distance_m) && (
                    <span className="ml-2">{formatDistance(venue.distance_m)}</span>
                  )}
                  {venue.hours?.open_now !== undefined && (
                    <span className="ml-2">
                      <OpenClosedBadge hours={venue.hours} />
                    </span>
                  )}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
