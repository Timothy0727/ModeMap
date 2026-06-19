"use client";

import { useEffect, useState } from "react";

import { getVenueProfile, type VenueProfile, type RecommendVenue } from "@/lib/api";

interface VenueDetailPanelProps {
  venue: RecommendVenue;
  rank: number;
  onClose: () => void;
}

function OpenBadge({ hours }: { hours: Record<string, unknown> | null }) {
  if (!hours || hours.open_now === undefined) return null;
  const isOpen = Boolean(hours.open_now);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
        isOpen
          ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400"
          : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400"
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${isOpen ? "bg-green-500" : "bg-red-500"}`}
      />
      {isOpen ? "Open now" : "Closed"}
    </span>
  );
}

function DirectionsLink({ lat, lng, name }: { lat: number; lng: number; name: string }) {
  const url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&destination_place_id=&query=${encodeURIComponent(name)}`;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
    >
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498 4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 0 0-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0Z" />
      </svg>
      Directions
    </a>
  );
}

/** Display label + icon for each canonical attribute key. */
const ATTRIBUTE_META: Record<string, { label: string; icon: string }> = {
  quiet: { label: "Quiet", icon: "🤫" },
  laptop_friendly: { label: "Laptop-friendly", icon: "💻" },
  romantic: { label: "Romantic", icon: "✨" },
  fast_service: { label: "Quick service", icon: "⚡" },
  value: { label: "Good value", icon: "💰" },
};

/** Minimum score to display an attribute tag (avoids showing very weak signals). */
const SCORE_THRESHOLD = 0.4;

function AttributeTags({ profile }: { profile: VenueProfile }) {
  const visible = Object.entries(profile.attribute_scores)
    .filter(([, score]) => score >= SCORE_THRESHOLD)
    .sort(([, a], [, b]) => b - a);

  if (visible.length === 0) return null;

  return (
    <div className="mt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
        Vibe
      </h3>
      <div className="mt-2 flex flex-wrap gap-2">
        {visible.map(([attr, score]) => {
          const meta = ATTRIBUTE_META[attr] ?? { label: attr, icon: "•" };
          const evidence = profile.evidence_snippets[attr]?.[0];
          return (
            <div key={attr} className="group relative">
              <span className="inline-flex cursor-default items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 ring-1 ring-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:ring-blue-800">
                <span>{meta.icon}</span>
                {meta.label}
                <span className="ml-0.5 text-blue-400 dark:text-blue-500">
                  {Math.round(score * 100)}%
                </span>
              </span>
              {evidence && (
                <div className="pointer-events-none absolute bottom-full left-0 z-10 mb-1.5 hidden w-56 rounded-md border border-zinc-200 bg-white p-2 text-xs text-zinc-600 shadow-lg group-hover:block dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
                  &ldquo;{evidence}&rdquo;
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function VenueDetailPanel({ venue, rank, onClose }: VenueDetailPanelProps) {
  const [profile, setProfile] = useState<VenueProfile | null>(null);

  useEffect(() => {
    getVenueProfile(venue.provider_id).then(setProfile).catch(() => setProfile(null));
  }, [venue.provider_id]);

  const weekdayText = (venue.hours as { weekday_text?: string[] } | null)?.weekday_text;
  const distanceLabel =
    venue.distance_m != null
      ? venue.distance_m < 1000
        ? `${Math.round(venue.distance_m)} m away`
        : `${(venue.distance_m / 1000).toFixed(1)} km away`
      : null;

  return (
    <div className="flex flex-col gap-4">
      {/* Back button */}
      <button
        type="button"
        onClick={onClose}
        className="flex items-center gap-1.5 self-start text-sm text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
        </svg>
        Back to list
      </button>

      {/* Main card */}
      <div className="rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-700 dark:bg-zinc-900">
        {/* Rank + Name */}
        <div className="flex items-start gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
            {rank}
          </span>
          <h2 className="text-lg font-semibold text-black dark:text-white leading-snug">
            {venue.name}
          </h2>
        </div>

        {/* Rating + Price + Distance + Open badge */}
        <div className="mt-3 flex flex-wrap items-center gap-3">
          {venue.rating !== null && (
            <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              ⭐ {venue.rating}
            </span>
          )}
          {venue.price_level !== null && (
            <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
              {"$".repeat(venue.price_level)}
            </span>
          )}
          {distanceLabel && (
            <span className="text-sm text-zinc-500 dark:text-zinc-400">{distanceLabel}</span>
          )}
          <OpenBadge hours={venue.hours} />
        </div>

        {/* Categories */}
        {venue.categories.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {venue.categories.map((cat) => (
              <span
                key={cat}
                className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
              >
                {cat}
              </span>
            ))}
          </div>
        )}

        {/* Divider */}
        <hr className="my-4 border-zinc-200 dark:border-zinc-700" />

        {/* Address + Directions */}
        {venue.address && (
          <div className="flex flex-col gap-1.5">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">{venue.address}</p>
            <DirectionsLink lat={venue.lat} lng={venue.lng} name={venue.name} />
          </div>
        )}

        {/* Hours */}
        {(weekdayText || venue.raw_hours) && (
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
              Hours
            </h3>
            {weekdayText ? (
              <ul className="mt-1.5 space-y-0.5 text-sm text-zinc-600 dark:text-zinc-400">
                {weekdayText.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : venue.raw_hours ? (
              <p className="mt-1.5 whitespace-pre-line text-sm text-zinc-600 dark:text-zinc-400">
                {venue.raw_hours}
              </p>
            ) : null}
          </div>
        )}

        {/* Explanations from mode-specific scoring (Step 4) */}
        {venue.explanations && venue.explanations.length > 0 && (
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
              Why this matches
            </h3>
            <ul className="mt-1.5 space-y-1">
              {venue.explanations.map((text, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-zinc-600 dark:text-zinc-400">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
                  {text}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Heuristic attribute tags + evidence (Step 5) */}
        {profile && <AttributeTags profile={profile} />}
      </div>
    </div>
  );
}
