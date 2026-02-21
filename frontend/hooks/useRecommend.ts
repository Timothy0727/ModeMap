"use client";

import { useState, useEffect, useCallback } from "react";
import { recommend, type Mode, type RecommendVenue } from "@/lib/api";

const DEFAULT_LAT = 37.7749;
const DEFAULT_LNG = -122.4194;
const DEFAULT_RADIUS = 1000;

export function useRecommend() {
  const [mode, setMode] = useState<Mode>("work");
  const [radius, setRadius] = useState(DEFAULT_RADIUS);
  const [openNow, setOpenNow] = useState(false);
  const [price, setPrice] = useState<number | undefined>(undefined);
  const [venues, setVenues] = useState<RecommendVenue[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedVenueId, setSelectedVenueId] = useState<string | null>(null);
  const [snap, setSnap] = useState<number | string | null>(0.15);

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

  const onVenueSelect = useCallback((venue: RecommendVenue) => {
    setSelectedVenueId((prev) => {
      const next = prev === venue.id ? null : venue.id;
      if (next) setSnap(0.5);
      return next;
    });
  }, []);

  const onCloseDetail = useCallback(() => {
    setSelectedVenueId(null);
  }, []);

  const selectedVenue = venues.find((v) => v.id === selectedVenueId) ?? null;
  const selectedRank = selectedVenue ? venues.indexOf(selectedVenue) + 1 : 0;

  return {
    mode,
    onModeChange: setMode,
    radius,
    onRadiusChange: setRadius,
    openNow,
    onOpenNowChange: setOpenNow,
    price,
    onPriceChange: setPrice,
    venues,
    loading,
    error,
    selectedVenueId,
    selectedVenue,
    selectedRank,
    onVenueSelect,
    onCloseDetail,
    snap,
    setSnap,
  };
}
