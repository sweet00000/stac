# SPEC.md

## 🚀 Project Goal
Refactor the existing "Django Map Demo" into a **STAC (SpatioTemporal Asset Catalog) Streamer**.
The application should allow a user to pan/zoom a Leaflet map, automatically querying a remote STAC API for satellite imagery footprints matching the current map view, and displaying them.

## 📂 File Structure Goals
Refactor the single `index.html` into:
1.  `index.html`: The UI, Leaflet logic, and Pyodide bootstrap.
2.  `backend.py`: The Django settings, models, and views (to be loaded into Pyodide's virtual filesystem).

## ⚡️ API Endpoints (Django Views)

### 1. `GET /api/stac/search/`
* **Parameters:**
    * `bbox`: Comma-separated string `min_lon,min_lat,max_lon,max_lat`.
    * `limit`: Integer (default 10).
* **Logic:**
    1.  Parse the bbox.
    2.  Use `requests` to query a public STAC API (e.g., Earth Search AWS or Microsoft Planetary Computer).
        * *Target API:* `https://earth-search.aws.element84.com/v1/search`
    3.  Filter for a specific collection (e.g., `sentinel-2-l2a`).
    4.  Save metadata (ID, footprint, date) to the local Django SQLite DB to act as a cache.
    5.  Return a **GeoJSON FeatureCollection** of the results.

### 2. `GET /api/stac/clear/`
* **Logic:** Clears the local SQLite database.

## 🗺️ Frontend (Leaflet) Requirements

### 1. Map Interaction
* Remove the manual "Fetch Data" button.
* Add a listener to the map's `moveend` event.
* **Debounce** the event (wait 500ms after movement stops).
* Get the current map bounds (`map.getBounds()`).
* Format bounds into a BBOX string.
* Call the Python Bridge: `/api/stac/search/?bbox=...`

### 2. Visualization
* Create a Leaflet `L.geoJSON` layer.
* When data returns from the API, clear the existing layer and populate it with the new footprints.
* **Popup:** Clicking a footprint should show the Scene ID and Timestamp.

## 🐍 Python/Django Implementation Details
* **Dependencies:** Add `pystac` (if available via micropip) or simply use `requests` to parse JSON.
* **Models:** Update `GISPoint` to a `StacItem` model:
    * `stac_id` (CharField)
    * `geometry` (JSONField or TextField to store GeoJSON)
    * `datetime` (DateTimeField)
* **Mocking:** Keep the `base_app` module mocking strategy to ensure Django finds the app without a physical file structure.

## ✅ Definition of Done
1.  User loads page.
2.  Map centers on a location.
3.  User pans the map.
4.  Network tab shows a request to the AWS STAC API (via Pyodide).
5.  Map displays blue polygons representing Sentinel-2 footprints for that area.
6.  Django SQLite DB contains the cached records.
