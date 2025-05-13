import base64
import duckdb
import re
from typing import List, Tuple
from tools.tool_definitions import get_full_topic_details_tool_name

class _OfflineWikipediaService:
    def __init__(self):
        self._db_path = "../data/wiki/wiki.db"
        self._connection = duckdb.connect(database=self._db_path, read_only=True)
        
    @staticmethod
    def merge_intervals(intervals: List[Tuple[int, int]], gap: int = 0) -> List[Tuple[int, int]]:
        if not intervals:
            return []
        intervals = sorted(intervals, key=lambda x: x[0])
        merged = [intervals[0]]
        for start, end in intervals[1:]:
            prev_start, prev_end = merged[-1]
            if start <= prev_end + gap:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))
        return merged

    def extract_contexts(self, text: str, term: str, ctx: int = 50) -> List[str]:
        lower_text = text.lower()
        spans: List[Tuple[int, int]] = [(0, min(len(text), 400))]
        for word in term.split():
            lw = word.lower()
            for m in re.finditer(re.escape(lw), lower_text):
                spans.append((m.start(), m.end()))

        if not spans:
            return []

        merged = self.merge_intervals(spans, gap=ctx)
        snippets: List[str] = []
        full_len = len(text)

        for start, end in merged:
            cs = max(0, start - ctx)
            ce = min(full_len, end + ctx)
            snippet = text[cs:ce].strip()
            if cs > 0:
                snippet = "… " + snippet
            if ce < full_len:
                snippet += " …"
            snippets.append(snippet)

        return snippets
        
    def fulltext_search(self, terms):
        search_terms = terms[:5]
        all_results = []
        seen = set()
        match_no = 1

        for term in search_terms:
            query = """
            SELECT
                title,
                text,
                fts_main_articles.match_bm25(rowid, ?) AS score
            FROM articles
            WHERE score IS NOT NULL
            ORDER BY score DESC
            LIMIT 15;
            """
            cur = self._connection.cursor()
            rows = cur.execute(query, [term]).fetchall()
            cur.close()

            for title, text, score in rows:
                topic_id = base64.b64encode(title.encode()).decode()
                if topic_id in seen:
                    continue
                seen.add(topic_id)

                contexts = self.extract_contexts(text, term, ctx=50)
                if not contexts:
                    print(f"No contexts found for term: {term}")
                    continue

                best_context = contexts[0]
                for snippet in contexts[1:]:
                    best_context = best_context.rstrip(" …")
                    snippet = snippet.lstrip("… ")
                    best_context = f"{best_context} … {snippet}"
                    
                if len(best_context) > 5500:
                    print(f"Truncating context for {title} from {len(best_context)} to 5500")
                    best_context = best_context[:5500].rstrip() + " …"

                all_results.append({
                    "content": (
                        f"# [{match_no}]: {title}\n\n"
                        f"{best_context}\n\n"
                        "LLMs: Content is truncated. "
                        f"Use the `{get_full_topic_details_tool_name}(['{topic_id}'])` tool "
                        "to unlock full topic details."
                    ),
                    "score": score
                })
                match_no += 1

        return "\n\n---\n\n".join(r["content"] for r in all_results[:25])
        
    def get_full_wikipedia_article(self, topic_ids):
        results = []
        for topic_id in topic_ids:
            try:
                title = base64.b64decode(topic_id).decode("utf-8")
            except Exception as e:
                print(f"Error decoding topic_id '{topic_id}': {e}")
                results.append(f"Error decoding topic_id '{topic_id}': {e}")
                continue
                
            cursor = self._connection.cursor()
            article = cursor.execute("""
                SELECT text FROM articles WHERE title = ?
            """, [title]).fetchone()
            cursor.close()
            
            if not article:
                results.append(f"Article not found for title: {title}")
                continue

            results.append(article[0])
        
        return "\n\n---\n\n".join(results)
    
offline_wikipedia_service = _OfflineWikipediaService()