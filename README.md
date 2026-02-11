# stac

Browser-native STAC streamer using Pyodide + Django + Leaflet.

## File layout
- `index.html`: frontend map/bootstrap.
- `backend.py`: Django views and STAC search/cache logic loaded into Pyodide FS.

## Streamable output
`/api/stac/search/` returns GeoJSON and keeps image-like STAC assets in `properties.streamable_assets` so links can be opened/streamed directly from popup UIs.
