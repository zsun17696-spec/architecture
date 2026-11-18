from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
CLEAN = DATA / "clean"
CHUNKS_DIR = DATA / "chunks"
DB_PATH = DATA / "warehouse.sqlite"
EVAL_DIR = ROOT / "eval"
WEB_DIST = ROOT / "web" / "dist"
