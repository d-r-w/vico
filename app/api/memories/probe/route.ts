import { INFERENCE_API_URL } from "@/app/api/config";

export async function POST(request: Request) {
  try {
    const { query, isDeep } = await request.json();
    if (!query?.trim()) {
      return new Response(JSON.stringify({ error: "Query is required" }), { status: 400 });
    }

    const url = new URL(`${INFERENCE_API_URL}${isDeep ? "probe_memories" : "chat_with_memories"}`);
    url.searchParams.set("query", query);
    const res = await fetch(url);

    if (!res.ok) {
      return new Response(JSON.stringify({ error: "Failed to probe memories" }), { status: 500 });
    }

    return new Response(res.body); // Stream directly
  } catch (error) {
    console.error("Failed to probe memories:", error);
    return new Response(JSON.stringify({ error: "Failed to probe memories" }), { status: 500 });
  }
}