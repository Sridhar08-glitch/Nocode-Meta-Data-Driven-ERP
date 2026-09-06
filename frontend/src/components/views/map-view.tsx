"use client";

import { extractMarkers } from "@/lib/views/map";
import { type Row } from "@/lib/views/types";

export interface MapViewProps {
  rows: Row[];
  latField: string;
  lngField: string;
  labelField?: string;
}

/**
 * Coordinate marker plot (Phase F2.1). Dependency-free projection of geospatial points into a
 * normalized box — an interactive basemap (MapLibre/OSM) is a deferred enhancement.
 */
export function MapView({ rows, latField, lngField, labelField }: MapViewProps) {
  const markers = extractMarkers(rows, latField, lngField, labelField);
  if (markers.length === 0) {
    return <p className="text-sm text-muted-foreground">No located records.</p>;
  }

  return (
    <div
      role="img"
      aria-label={`Map with ${markers.length} markers`}
      className="relative aspect-video w-full rounded-md border bg-muted/30"
    >
      {markers.map((m) => (
        <span
          key={m.id}
          title={m.label}
          aria-label={m.label}
          style={{ left: `${m.x}%`, top: `${m.y}%` }}
          className="absolute size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary ring-2 ring-background"
        />
      ))}
    </div>
  );
}
