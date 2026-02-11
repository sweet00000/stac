import json
import os
import sys
import types
from datetime import datetime
from urllib.parse import urlparse

import requests
from django.apps import AppConfig
from django.conf import settings
from django.db import connection, models
from django.http import HttpResponse, JsonResponse
from django.test import Client
from django.urls import path
from django.views.decorators.http import require_GET
from pyodide_http import patch_all

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
DEFAULT_STAC_API = "https://earth-search.aws.element84.com/v1"


class BaseAppConfig(AppConfig):
    name = "base_app"
    label = "base_app"
    path = os.getcwd()


def _mock_base_app() -> None:
    if "base_app" in sys.modules:
        return

    base_app_module = types.ModuleType("base_app")
    apps_module = types.ModuleType("base_app.apps")
    apps_module.BaseAppConfig = BaseAppConfig
    base_app_module.default_app_config = "base_app.apps.BaseAppConfig"

    sys.modules["base_app"] = base_app_module
    sys.modules["base_app.apps"] = apps_module


def _configure_django() -> None:
    if settings.configured:
        return

    settings.configure(
        DEBUG=True,
        SECRET_KEY="stac-demo",
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=["*"],
        MIDDLEWARE=[],
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "base_app.apps.BaseAppConfig",
        ],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        DEFAULT_AUTO_FIELD="django.db.models.AutoField",
    )


def _bootstrap_runtime() -> None:
    patch_all()
    _mock_base_app()
    _configure_django()

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


_bootstrap_runtime()


class StacItem(models.Model):
    stac_id = models.CharField(max_length=255, unique=True)
    collection = models.CharField(max_length=255, default="")
    api_url = models.CharField(max_length=1024, default=DEFAULT_STAC_API)
    geometry = models.TextField()
    datetime = models.DateTimeField(null=True, blank=True)
    assets = models.TextField(default="{}")

    class Meta:
        app_label = "base_app"


def _ensure_schema() -> None:
    existing_tables = connection.introspection.table_names()
    if StacItem._meta.db_table in existing_tables:
        return

    with connection.schema_editor() as editor:
        editor.create_model(StacItem)


def _parse_datetime(raw_value: str | None):
    if not raw_value:
        return None

    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_api_url(raw_value: str | None) -> str:
    candidate = (raw_value or DEFAULT_STAC_API).strip().rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("api_url must be a valid http(s) URL")
    return candidate


def _extract_streamable_assets(raw_assets: dict | None) -> dict:
    if not isinstance(raw_assets, dict):
        return {}

    kept_assets = {}
    for key, asset in raw_assets.items():
        if not isinstance(asset, dict):
            continue

        href = asset.get("href")
        media_type = (asset.get("type") or "").lower()
        role_blob = " ".join(asset.get("roles", [])).lower()
        is_image = "image" in media_type or "visual" in role_blob or "thumbnail" in role_blob
        if href and is_image:
            kept_assets[key] = {
                "href": href,
                "type": media_type,
                "title": asset.get("title", ""),
                "roles": asset.get("roles", []),
            }

    return kept_assets


def _to_geojson_feature(item: StacItem) -> dict:
    return {
        "type": "Feature",
        "id": item.stac_id,
        "geometry": json.loads(item.geometry),
        "properties": {
            "stac_id": item.stac_id,
            "collection": item.collection,
            "api_url": item.api_url,
            "datetime": item.datetime.isoformat() if item.datetime else None,
            "streamable_assets": json.loads(item.assets),
        },
    }


@require_GET
def stac_collections(request):
    try:
        api_url = _normalize_api_url(request.GET.get("api_url"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        response = requests.get(f"{api_url}/collections", timeout=20)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return JsonResponse({"error": f"Failed to fetch collections: {exc}"}, status=502)

    collections = []
    for collection in payload.get("collections", []):
        collections.append(
            {
                "id": collection.get("id"),
                "title": collection.get("title") or collection.get("id"),
                "description": collection.get("description", ""),
            }
        )

    return JsonResponse({"api_url": api_url, "collections": collections})


@require_GET
def stac_search(request):
    bbox_param = request.GET.get("bbox", "")
    limit_param = request.GET.get("limit", "10")
    collection = (request.GET.get("collection", "sentinel-2-l2a") or "").strip()

    if not collection:
        return JsonResponse({"error": "collection is required"}, status=400)

    try:
        api_url = _normalize_api_url(request.GET.get("api_url"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        bbox = [float(value) for value in bbox_param.split(",")]
        if len(bbox) != 4:
            raise ValueError("bbox must include min_lon,min_lat,max_lon,max_lat")
    except ValueError as exc:
        return JsonResponse({"error": f"Invalid bbox: {exc}"}, status=400)

    try:
        limit = max(1, min(int(limit_param), 100))
    except ValueError:
        return JsonResponse({"error": "Invalid limit. Must be an integer."}, status=400)

    payload = {
        "collections": [collection],
        "bbox": bbox,
        "limit": limit,
    }

    try:
        response = requests.post(
            f"{api_url}/search",
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return JsonResponse({"error": f"Failed to fetch STAC data: {exc}"}, status=502)

    features = []
    for feature in data.get("features", []):
        geometry = feature.get("geometry")
        stac_id = feature.get("id")
        if not geometry or not stac_id:
            continue

        streamable_assets = _extract_streamable_assets(feature.get("assets"))
        dt = _parse_datetime(feature.get("properties", {}).get("datetime"))

        item, _ = StacItem.objects.update_or_create(
            stac_id=stac_id,
            defaults={
                "collection": collection,
                "api_url": api_url,
                "geometry": json.dumps(geometry),
                "datetime": dt,
                "assets": json.dumps(streamable_assets),
            },
        )
        features.append(_to_geojson_feature(item))

    return JsonResponse({"type": "FeatureCollection", "features": features})


@require_GET
def stac_clear(_request):
    deleted_count, _ = StacItem.objects.all().delete()
    return JsonResponse({"status": "ok", "deleted": deleted_count})


def health(_request):
    return HttpResponse("ok")


urlpatterns = [
    path("api/stac/collections/", stac_collections),
    path("api/stac/search/", stac_search),
    path("api/stac/clear/", stac_clear),
    path("health/", health),
]


def handle_request(path_with_query: str) -> str:
    client = Client()
    response = client.get(path_with_query)
    return response.content.decode("utf-8")


_ensure_schema()
