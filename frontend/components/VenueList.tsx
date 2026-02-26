"use client";

import { type RecommendVenue } from "@/lib/api";

interface VenueListProps {
  venues: RecommendVenue[];
  onVenueSelect: (venue: RecommendVenue) => void;
}

export default function VenueList({ venues, onVenueSelect }: VenueListProps) {
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
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
