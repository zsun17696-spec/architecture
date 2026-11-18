from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
CLEAN = DATA / "clean"
CHUNKS_DIR = DATA / "chunks"
PAGES = DATA / "pages"
DB_PATH = DATA / "warehouse.sqlite"
EVAL_DIR = ROOT / "eval"
MANIFEST = RAW / "manifest.json"
WEB_DIST = ROOT / "apps" / "web" / "dist"
