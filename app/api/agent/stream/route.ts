import { NextResponse } from "next/server";
import { INFERENCE_API_URL } from "@/app/api/config";

export async function POST(request: Request) {
  try {
    const body: { query?: unknown } = await request.json();
    const query = typeof body.query === "string" ? body.query.trim() : "";

    if (!query) {
      return NextResponse.json({ error: "Query is required" }, { status: 400 });
    }

    const url = new URL(`${INFERENCE_API_URL}agent/stream/`);
    url.searchParams.set("query", query);
    const res = await fetch(url);

    if (!res.ok) {
      throw new Error(`Response not ok: ${res.status}`);
    }

    return new NextResponse(res.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
      status: res.status,
    });
  } catch (error) {
    console.error("Failed to stream agent response:", error);
    return NextResponse.json(
      { error: "Failed to stream agent response" },
      { status: 500 }
    );
  }
}
