"use client";
import Image from "next/image";
import { useState } from 'react';
import { searchVenues, Venue } from "@/lib/api";
import Map from "@/components/Map";


export default function Home() {

  // In a React component:
  const [venues, setVenues] = useState<Venue[]>([]);
  const [loading, setLoading] = useState(false);

  async function loadVenues(lat: number, lng: number) {
    setLoading(true);
    try {
      const results = await searchVenues({ lat, lng, radius: 1000 });
      setVenues(results);
    } catch (error) {
      console.error("Failed to load venues:", error);
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex min-h-screen w-full max-w-3xl flex-col items-center justify-between py-32 px-16 bg-white dark:bg-black sm:items-start">
        <h1 className="text-3xl font-semibold text-black dark:text-zinc-50">
          ModeMap
        </h1>

        {/* Test button to load venues */}
        <button
          onClick={() => loadVenues(37.7749, -122.4194)}
          disabled={loading}
          className="rounded-full bg-foreground px-5 py-3 text-background hover:bg-[#383838]"
        >
          {loading ? "Loading..." : "Load Venues (SF)"}
        </button>

        {/* Map section */}
        <div className="w-full h-[400px]">
          <Map className="w-full h-full" venues={venues} />
        </div>

        {/* Display venues */}
        <div className="mt-4 w-full">
          <p className="text-zinc-600 dark:text-zinc-400">
            Found {venues.length} venues
          </p>
          <ul className="mt-2 space-y-2">
            {venues.map((venue) => (
              <li
                key={venue.provider_id}
                className="rounded border p-2 text-black dark:text-white"
              >
                {venue.name} - {venue.rating ?? "N/A"} ⭐
              </li>
            ))}
          </ul>
        </div>
      </main>
    </div>
  );
}
