D=$(date +%Y%m01)
BASE=https://dumps.wikimedia.org/enwiki/$D
curl -L -O -C - "$BASE/enwiki-${D}-pages-articles-multistream.xml.bz2"
curl -L -O -C - "$BASE/enwiki-${D}-pages-articles-multistream-index.txt.bz2"
uv run -- wikiextractor --json --processes 12 --output extracted_json enwiki-${D}-pages-articles-multistream.xml.bz2
duckdb wiki.db < import.sql

