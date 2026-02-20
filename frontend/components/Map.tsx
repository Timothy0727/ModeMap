"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { type RecommendVenue } from "@/lib/api";

mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

const SOURCE_ID = "venues";
const CIRCLE_LAYER = "venues-circles";
const LABEL_LAYER = "venues-labels";

interface MapProps {
  initialCenter?: [number, number];
  initialZoom?: number;
  className?: string;
  venues?: RecommendVenue[];
  selectedVenueId?: string | null;
  onMarkerClick?: (venue: RecommendVenue) => void;
}

function buildGeoJSON(
  venues: RecommendVenue[],
  selectedId: string | null
): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: venues.map((v, i) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [v.lng, v.lat] },
      properties: {
        id: v.id,
        rank: i + 1,
        name: v.name,
        rating: v.rating,
        price_level: v.price_level,
        categories: v.categories.join(", "),
        address: v.address ?? "",
        selected: v.id === selectedId ? 1 : 0,
      },
    })),
  };
}

function popupHTML(props: Record<string, unknown>): string {
  const priceStr = props.price_level
    ? " · " + "$".repeat(props.price_level as number)
    : "";
  return `
    <div style="color:#111; font-size:13px; line-height:1.4; max-width:220px;">
      <strong>#${props.rank} ${props.name}</strong><br/>
      ${props.rating ? `⭐ ${props.rating}` : ""}${priceStr}<br/>
      <span style="color:#666">${props.categories}</span><br/>
      <span style="color:#888; font-size:12px">${props.address}</span>
    </div>`;
}

export default function Map({
  initialCenter = [-122.4194, 37.7749],
  initialZoom = 13,
  className = "w-full h-[500px]",
  venues = [],
  selectedVenueId = null,
  onMarkerClick,
}: MapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const popupRef = useRef<mapboxgl.Popup | null>(null);
  const [mapReady, setMapReady] = useState(false);

  // Stable refs so the init effect never re-runs due to prop identity changes
  const initCenter = useRef(initialCenter);
  const initZoom = useRef(initialZoom);

  // Refs for latest values so event handlers don't go stale
  const venuesById = useRef<Record<string, RecommendVenue>>({});
  const onClickRef = useRef(onMarkerClick);
  useEffect(() => { onClickRef.current = onMarkerClick; }, [onMarkerClick]);
  useEffect(() => {
    venuesById.current = Object.fromEntries(venues.map((v) => [v.id, v]));
  }, [venues]);

  // Initialize map once
  useEffect(() => {
    if (mapRef.current || !mapContainer.current) return;

    const m = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/streets-v12",
      center: initCenter.current,
      zoom: initZoom.current,
    });

    m.addControl(new mapboxgl.NavigationControl(), "top-right");

    popupRef.current = new mapboxgl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 14,
    });

    m.on("load", () => {
      m.addSource(SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      m.addLayer({
        id: CIRCLE_LAYER,
        type: "circle",
        source: SOURCE_ID,
        layout: {
          "circle-sort-key": ["case", ["==", ["get", "selected"], 1], 1, 0],
        },
        paint: {
          "circle-radius": ["case", ["==", ["get", "selected"], 1], 14, 11],
          "circle-color": ["case", ["==", ["get", "selected"], 1], "#ef4444", "#3b82f6"],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      m.addLayer({
        id: LABEL_LAYER,
        type: "symbol",
        source: SOURCE_ID,
        layout: {
          "text-field": ["to-string", ["get", "rank"]],
          "text-size": 11,
          "text-font": ["DIN Pro Medium", "Arial Unicode MS Bold"],
          "text-allow-overlap": true,
          "text-ignore-placement": true,
        },
        paint: {
          "text-color": "#ffffff",
        },
      });

      // Click handler
      m.on("click", CIRCLE_LAYER, (e) => {
        const id = e.features?.[0]?.properties?.id;
        if (id && venuesById.current[id]) {
          onClickRef.current?.(venuesById.current[id]);
        }
      });

      // Hover popup
      m.on("mouseenter", CIRCLE_LAYER, (e) => {
        m.getCanvas().style.cursor = "pointer";
        const feature = e.features?.[0];
        if (feature && feature.geometry.type === "Point" && popupRef.current) {
          popupRef.current
            .setLngLat(feature.geometry.coordinates as [number, number])
            .setHTML(popupHTML(feature.properties ?? {}))
            .addTo(m);
        }
      });

      m.on("mouseleave", CIRCLE_LAYER, () => {
        m.getCanvas().style.cursor = "";
        popupRef.current?.remove();
      });

      setMapReady(true);
    });

    mapRef.current = m;

    return () => {
      popupRef.current?.remove();
      m.remove();
      mapRef.current = null;
      setMapReady(false);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update GeoJSON data when venues, selection, or map readiness changes
  useEffect(() => {
    if (!mapRef.current || !mapReady) return;
    const source = mapRef.current.getSource(SOURCE_ID) as mapboxgl.GeoJSONSource | undefined;
    if (source) {
      source.setData(buildGeoJSON(venues, selectedVenueId));
    }
  }, [venues, selectedVenueId, mapReady]);

  // Fly to selected venue
  useEffect(() => {
    if (!mapRef.current || !selectedVenueId) return;
    const venue = venuesById.current[selectedVenueId];
    if (venue) {
      mapRef.current.flyTo({
        center: [venue.lng, venue.lat],
        zoom: Math.max(mapRef.current.getZoom(), 14),
        duration: 600,
      });
    }
  }, [selectedVenueId]);

  return <div ref={mapContainer} className={className} />;
}
