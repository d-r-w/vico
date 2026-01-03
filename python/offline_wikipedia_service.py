import duckdb
import logging
import re
import uuid
from typing import List, Tuple
from tools.tool_definitions import get_full_topic_details_tool_name

logger = logging.getLogger("offline_wikipedia")

class _OfflineWikipediaService:
    def __init__(self):
        self._db_path = "../data/wiki/wiki.db"
        self._connection = duckdb.connect(database=self._db_path, read_only=True)
        self._id_to_title = {}
        self._title_to_id = {}
        
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

    def remove_consecutive_short_lines(self, text: str, max_line_length: int = 100, min_consecutive: int = 3) -> str:
        """
        Remove consecutive blocks of short lines that are likely noise.
        
        Args:
            text: The input text to clean
            max_line_length: Maximum length of a line to be considered "short"
            min_consecutive: Minimum number of consecutive short lines to trigger removal
            
        Returns:
            Cleaned text with consecutive short line blocks removed
        """
        lines = text.split('\n')
        if len(lines) < min_consecutive:
            return text
            
        # Track which lines to keep
        keep_lines = [True] * len(lines)
        
        # Find consecutive blocks of short lines
        i = 0
        while i < len(lines):
            # Check if current line is short
            if len(lines[i].strip()) < max_line_length:
                # Count consecutive short lines
                consecutive_count = 0
                j = i
                while j < len(lines) and len(lines[j].strip()) < max_line_length:
                    consecutive_count += 1
                    j += 1
                
                # If we have enough consecutive short lines, mark them for removal
                if consecutive_count >= min_consecutive:
                    for k in range(i, j):
                        keep_lines[k] = False
                    i = j
                else:
                    i += 1
            else:
                i += 1
        
        # Filter out the lines marked for removal
        filtered_lines = [line for line, keep in zip(lines, keep_lines) if keep]
        
        # Clean up multiple consecutive empty lines
        result_lines = []
        prev_empty = False
        for line in filtered_lines:
            is_empty = len(line.strip()) == 0
            if not (is_empty and prev_empty):  # Skip if both current and previous are empty
                result_lines.append(line)
            prev_empty = is_empty
        
        return '\n'.join(result_lines)

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
        search_terms = [t.strip() for t in terms[:5] if t.strip()]
        if not search_terms:
            return ""

        # Combine terms with OR for DuckDB FTS
        fts_query = " OR ".join(search_terms)
        
        query = """
        SELECT
            title,
            text,
            fts_main_articles.match_bm25(rowid, ?) AS score
        FROM articles
        WHERE score IS NOT NULL
        ORDER BY score DESC
        LIMIT 25;
        """
        
        cur = self._connection.cursor()
        rows = cur.execute(query, [fts_query]).fetchall()
        cur.close()

        all_results = []
        seen = set()
        match_no = 1
        
        # For context extraction, join all terms to find matches for any of them
        context_query = " ".join(search_terms)

        for title, text, score in rows:
            if title not in self._title_to_id:
                topic_id = str(uuid.uuid4())
                self._title_to_id[title] = topic_id
                self._id_to_title[topic_id] = title
            else:
                topic_id = self._title_to_id[title]

            if topic_id in seen:
                continue
            seen.add(topic_id)

            # Clean the text by removing consecutive short lines
            cleaned_text = self.remove_consecutive_short_lines(text)
            
            contexts = self.extract_contexts(cleaned_text, context_query, ctx=50)
            if not contexts:
                best_context = cleaned_text
            else:
                best_context = contexts[0]
                for snippet in contexts[1:]:
                    best_context = best_context.rstrip(" …")
                    snippet = snippet.lstrip("… ")
                    best_context = f"{best_context} … {snippet}"
                    
            if len(best_context) > 800:
                logger.debug(
                    "Truncating context for %s from %s to 800",
                    title,
                    len(best_context),
                )
                best_context = best_context[:800].rstrip() + " …"

            all_results.append({
                "content": (
                    f"# [{match_no}]: {title} ({topic_id})\n\n"
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
            title = self._id_to_title.get(topic_id)
            if not title:
                logger.warning("Topic ID %r not found in mapping", topic_id)
                results.append(f"Topic ID '{topic_id}' not found. Please run a new search to get valid IDs.")
                continue
                
            cursor = self._connection.cursor()
            article = cursor.execute("""
                SELECT text FROM articles WHERE title = ?
            """, [title]).fetchone()
            cursor.close()
            
            if not article:
                results.append(f"Article not found for title: {title}")
                continue

            # Clean the article text by removing consecutive short lines
            cleaned_article = self.remove_consecutive_short_lines(article[0])
            results.append(cleaned_article)
        
        return "\n\n---\n\n".join(results)
    
offline_wikipedia_service = _OfflineWikipediaService()