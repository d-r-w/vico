set -e
D=$(date +%Y%m01)
BASE=https://dumps.wikimedia.org/enwiki/$D

# TODO: If the file already exists, skip the download

curl -L -O -C - "$BASE/enwiki-${D}-pages-articles-multistream.xml.bz2"

# TODO: If the downloaded file is 0 bytes, delete it and exit (there's no update to download)

uv run -- wikiextractor --json --processes 12 --output extracted_json enwiki-${D}-pages-articles-multistream.xml.bz2

duckdb wiki.db <<EOF
INSTALL fts;  
LOAD fts;

CREATE TABLE IF NOT EXISTS articles AS
SELECT title, text
FROM read_json_auto('extracted_json/*/*');

PRAGMA create_fts_index('articles', 'rowid', 'text', overwrite=1);
EOF