import base64
import duckdb
import logging
from threading import Lock

db_path = '../data/memories.duckdb'

logger = logging.getLogger("memory_storage")

class _MemoriesStorageService:
    _instance = None
    _lock = Lock()
    _initialized = False
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            if not cls._initialized:
                cls._instance._initialize_schema()
                cls._initialized = True
        return cls._instance
    
    def _initialize_schema(self):
        conn = duckdb.connect(database=db_path, read_only=False)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE SEQUENCE IF NOT EXISTS memories_id_seq START 1;
            """)
            cursor.execute("""
                CREATE SEQUENCE IF NOT EXISTS tags_id_seq START 1;
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER DEFAULT nextval('memories_id_seq') PRIMARY KEY,
                    memory TEXT,
                    image BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER DEFAULT nextval('tags_id_seq') PRIMARY KEY,
                    label TEXT UNIQUE NOT NULL
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_tags (
                    memory_id INTEGER,
                    tag_id INTEGER,
                    PRIMARY KEY (memory_id, tag_id),
                    FOREIGN KEY (memory_id) REFERENCES memories(id),
                    FOREIGN KEY (tag_id) REFERENCES tags(id)
                );
            """)
            conn.commit()
            cursor.close()
        finally:
            conn.close()

def process_memory_rows(rows):
    processed_rows = []
    for memory_row in rows:
        # Unpack depending on expected columns (id, memory, image, created_at, tags)
        # We assume the query returns 5 columns now
        if len(memory_row) == 5:
             memory_id, memory, image, created_at, tags = memory_row
        else:
             # Fallback
             memory_id, memory, image, created_at = memory_row
             tags = []
        
        if image is not None:
            if isinstance(image, str):
                # Already encoded or string data
                image = image
            else:
                # Bytes data
                image = base64.b64encode(image).decode('utf-8')
            
        # Convert tags to list if it's None (DuckDB might return None for empty list in some versions/cases)
        if tags is None:
            tags = []
            
        processed_rows.append((memory_id, memory, image, created_at, tags))
    
    return processed_rows

def _execute_query(query, params=(), fetch=False):
    _MemoriesStorageService()  # Ensure schema is initialized
    conn = duckdb.connect(database=db_path, read_only=False)
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall() if fetch else None
        conn.commit()
        cursor.close()
        return results
    finally:
        conn.close()

def save_memory(memory, media = None, tag_ids = None):
    rows = _execute_query("""
        INSERT INTO memories (memory, image) VALUES (?, ?) RETURNING id;
    """, (memory, media), fetch=True)
    
    if not rows:
        return

    memory_id = rows[0][0]
    
    if tag_ids:
        for tag_id in tag_ids:
            try:
                _execute_query("""
                    INSERT INTO memory_tags (memory_id, tag_id) VALUES (?, ?);
                """, (memory_id, tag_id))
            except Exception as e:
                logger.warning(
                    "Error linking tag %s to memory %s",
                    tag_id,
                    memory_id,
                    exc_info=True,
                )
    
def delete_memory(memory_id):
    _execute_query("DELETE FROM memory_tags WHERE memory_id = ?", (memory_id,))
    _execute_query("""
        DELETE FROM memories WHERE id = ?;
    """, (memory_id,))

def add_tag(label):
    try:
        rows = _execute_query("""
            INSERT INTO tags (label) VALUES (?) RETURNING id;
        """, (label,), fetch=True)
        if rows:
            return rows[0][0]
    except Exception:
        try:
            rows = _execute_query("""
                SELECT id FROM tags WHERE label = ?;
            """, (label,), fetch=True)
            if rows:
                return rows[0][0]
        except Exception:
            pass
        return None

def delete_tag(tag_id):
    _execute_query("DELETE FROM memory_tags WHERE tag_id = ?", (tag_id,))
    _execute_query("""
        DELETE FROM tags WHERE id = ?;
    """, (tag_id,))

def get_all_tags():
    return _execute_query("""
        SELECT id, label FROM tags ORDER BY label;
    """, fetch=True)

def get_recent_memories(n):
    rows = _execute_query("""
        WITH recent AS (
            SELECT id, memory, image, created_at 
            FROM memories 
            ORDER BY created_at DESC 
            LIMIT ?
        )
        SELECT 
            m.id, 
            m.memory, 
            m.image, 
            m.created_at,
            list(t.label) FILTER (t.label IS NOT NULL) as tags
        FROM recent m
        LEFT JOIN memory_tags mt ON m.id = mt.memory_id
        LEFT JOIN tags t ON mt.tag_id = t.id
        GROUP BY m.id, m.memory, m.image, m.created_at
        ORDER BY m.created_at DESC;
    """, (n,), fetch=True)
    
    return process_memory_rows(rows)

def search_memories(search_terms):
    if isinstance(search_terms, str):
        search_terms = [search_terms]
    elif not isinstance(search_terms, (list, tuple)):
        raise ValueError("search_terms must be a string or a list/tuple of strings")

    where_clauses = []
    params = []
    for term in search_terms:
        where_clauses.append("(LOWER(m.memory) LIKE CONCAT('%', LOWER(?), '%') OR LOWER(t.label) LIKE CONCAT('%', LOWER(?), '%'))")
        params.append(term)
        params.append(term)
    where_sql = " OR ".join(where_clauses)

    query = f"""
        WITH matches AS (
            SELECT DISTINCT m.id, m.memory, m.image, m.created_at
            FROM memories m
            LEFT JOIN memory_tags mt ON m.id = mt.memory_id
            LEFT JOIN tags t ON mt.tag_id = t.id
            WHERE {where_sql}
            ORDER BY m.created_at DESC
            LIMIT 50
        )
        SELECT 
            m.id, 
            m.memory, 
            m.image, 
            m.created_at,
            list(t.label) FILTER (t.label IS NOT NULL) as tags
        FROM matches m
        LEFT JOIN memory_tags mt ON m.id = mt.memory_id
        LEFT JOIN tags t ON mt.tag_id = t.id
        GROUP BY m.id, m.memory, m.image, m.created_at
        ORDER BY m.created_at DESC;
    """

    rows = _execute_query(query, tuple(params), fetch=True)
    return process_memory_rows(rows)
    
def get_memories_by_tag_id(tag_id):
    rows = _execute_query("""
        WITH tagged AS (
            SELECT m.id, m.memory, m.image, m.created_at
            FROM memories m
            JOIN memory_tags mt ON m.id = mt.memory_id
            WHERE mt.tag_id = ?
            ORDER BY m.created_at DESC
            LIMIT 50
        )
        SELECT 
            m.id, 
            m.memory, 
            m.image, 
            m.created_at,
            list(t.label) FILTER (t.label IS NOT NULL) as tags
        FROM tagged m
        LEFT JOIN memory_tags mt ON m.id = mt.memory_id
        LEFT JOIN tags t ON mt.tag_id = t.id
        GROUP BY m.id, m.memory, m.image, m.created_at
        ORDER BY m.created_at DESC;
    """, (tag_id,), fetch=True)
    
    return process_memory_rows(rows)

def get_all_memories():
    return _execute_query("""
        SELECT 
            m.id, 
            m.created_at, 
            m.memory,
            list(t.label) FILTER (t.label IS NOT NULL) as tags
        FROM memories m
        LEFT JOIN memory_tags mt ON m.id = mt.memory_id
        LEFT JOIN tags t ON mt.tag_id = t.id
        GROUP BY m.id, m.created_at, m.memory
        ORDER BY m.created_at;
    """, fetch=True)

def edit_memory(memory_id, new_memory_text, tag_ids=None):
    _execute_query("""
        UPDATE memories SET memory = ? WHERE id = ?;
    """, (new_memory_text, memory_id))
    
    if tag_ids is not None:
        _execute_query("""
            DELETE FROM memory_tags WHERE memory_id = ?;
        """, (memory_id,))
        
        for tag_id in tag_ids:
            try:
                _execute_query("""
                    INSERT INTO memory_tags (memory_id, tag_id) VALUES (?, ?);
                """, (memory_id, tag_id))
            except Exception as e:
                print(f"Error linking tag {tag_id} to memory {memory_id}: {e}")