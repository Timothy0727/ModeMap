"use client";

import {useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { Venue } from "@/lib/api";

mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

interface MapProps {
  initialCenter?: [number, number]; // [lng, lat]
  initialZoom?: number;
  className?: string;
  venues?: Venue[];
}

export default function Map({
  initialCenter = [-122.4194, 37.7749], // San Francisco [lng, lat]
  initialZoom = 13,
  className = "w-full h-[500px]",
  venues = [],
}: MapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const markers = useRef<mapboxgl.Marker[]>([]);

  useEffect(() => {
    // Don't initialize if already exists or no container
    if (map.current || !mapContainer.current) return;

    // Initialize map
    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/streets-v12",
      center: initialCenter,
      zoom: initialZoom,
    });

    // Add navigation controls (zoom +/-)
    map.current.addControl(new mapboxgl.NavigationControl(), "top-right");

    // Cleanup on unmount
    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, [initialCenter, initialZoom]);

  useEffect(() => {
    if (!map.current) return;

    markers.current.forEach((marker) => marker.remove());
    markers.current = []

    venues.forEach((venue) => {
        const popup = new mapboxgl.Popup({ offset: 25 }).setHTML(`
            <!-- Edit marker display info here -->
            <div style="color: black;">
                <strong>${venue.name}</strong>
                <br/>
                ${venue.rating ? `⭐ ${venue.rating}` : ""}
                ${venue.price_level ? ` · ${"$".repeat(venue.price_level)}` : ""}
                <br/>
                ${venue.categories}
                <br/>
                ${venue.address}
            </div>
        `);
        const marker = new mapboxgl.Marker({ color: "#3b82f6" }) // Blue color
        .setLngLat([venue.lng, venue.lat])
        .setPopup(popup)
        .addTo(map.current!);

      markers.current.push(marker);
    });
  }, [venues]);
  return <div ref={mapContainer} className={className} />;
}