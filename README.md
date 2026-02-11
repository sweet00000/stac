# stac

Browser-native STAC streamer using Pyodide + Django + Leaflet.

## File layout
- `index.html`: frontend map/bootstrap + STAC explorer GUI controls.
- `backend.py`: Django views and STAC search/cache logic loaded into Pyodide FS.

## Streamable output
`/api/stac/search/` returns GeoJSON and keeps image-like STAC assets in `properties.streamable_assets` so links can be opened/streamed directly from popups.

## Explorer flow
1. Load STAC collections from a selected STAC API.
2. Filter/select a collection in the toolbar.
3. Pan/zoom the map to trigger debounced bbox search.
4. Open asset links from Leaflet popups for visualization/download/streaming.
