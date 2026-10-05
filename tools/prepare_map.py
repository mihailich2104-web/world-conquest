"""Скачивает Natural Earth 110m Admin 0 Countries и готовит src/data/provinces.geojson."""
from __future__ import annotations

import logging
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from config import PROVINCES_PATH, SIMPLIFY_TOLERANCE  # noqa: E402

URLS = [
    "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip",
    "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/110m/cultural/ne_110m_admin_0_countries.zip",
]
log = logging.getLogger("prepare_map")


def download(dest: Path) -> Path:
    """Скачивает и распаковывает архив (пробует зеркала), возвращает путь к .shp."""
    zpath = dest / "ne.zip"
    last: Exception | None = None
    for url in URLS:
        try:
            log.info("Загрузка %s", url)
            req = urllib.request.Request(url, headers={"User-Agent": "world-conquest/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(zpath, "wb") as f:
                f.write(r.read())
            with zipfile.ZipFile(zpath) as z:
                z.extractall(dest)
            return next(dest.glob("*.shp"))
        except Exception as exc:  # сеть/архив: пробуем следующее зеркало
            last = exc
            log.warning("Не удалось: %s", exc)
    raise RuntimeError(f"Natural Earth недоступен: {last}")


def main() -> None:
    """Формирует упрощённый GeoJSON с полями iso, name, continent."""
    logging.basicConfig(level=logging.INFO)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            gdf = gpd.read_file(download(Path(tmp)))
    except Exception:
        log.exception("Не удалось получить данные Natural Earth")
        raise SystemExit(1)

    # у Франции, Норвегии, Косово и др. ISO_A3 = -99 → берём ADM0_A3
    iso = gdf["ISO_A3"].where(gdf["ISO_A3"] != "-99", gdf["ADM0_A3"])
    out = gpd.GeoDataFrame(
        {"iso": iso, "name": gdf["NAME"], "continent": gdf["CONTINENT"]},
        geometry=gdf.geometry.simplify(SIMPLIFY_TOLERANCE),
        crs="EPSG:4326",
    )
    out = out[~out.geometry.is_empty]
    PROVINCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(PROVINCES_PATH, driver="GeoJSON")
    log.info("Сохранено %d стран → %s", len(out), PROVINCES_PATH)


if __name__ == "__main__":
    main()
