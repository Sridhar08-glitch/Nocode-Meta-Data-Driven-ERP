/** Map (Phase F2.1) — coordinate extraction + projection to a 0..100 box. Pure. */
import { type GeoMarker, type Row, rowId, toText } from "./types";

/** Extract valid lat/lng markers and project them into a 0..100 box (north at top). */
export function extractMarkers(
  rows: Row[],
  latField: string,
  lngField: string,
  labelField?: string,
): GeoMarker[] {
  const blank = (v: unknown) => v === null || v === undefined || v === "";
  const pts = rows
    .filter((row) => !blank(row[latField]) && !blank(row[lngField]))
    .map((row) => ({ row, lat: Number(row[latField]), lng: Number(row[lngField]) }))
    .filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lng) && Math.abs(p.lat) <= 90 && Math.abs(p.lng) <= 180);
  if (pts.length === 0) return [];
  const lats = pts.map((p) => p.lat);
  const lngs = pts.map((p) => p.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const spanLat = maxLat - minLat || 1;
  const spanLng = maxLng - minLng || 1;
  return pts.map(({ row, lat, lng }) => ({
    id: rowId(row),
    row,
    lat,
    lng,
    x: ((lng - minLng) / spanLng) * 100,
    y: ((maxLat - lat) / spanLat) * 100,
    label: toText(labelField ? row[labelField] : row.id),
  }));
}
