import { NextResponse } from "next/server";
import { INFERENCE_API_URL } from "@/app/api/config";

export async function POST(request: Request) {
  try {
    const { query, isDeep } = await request.json();
    if (!query?.trim()) {
      return NextResponse.json({ error: "Query is required" }, { status: 400 });
    }

    const url = new URL(
      `${INFERENCE_API_URL}${isDeep ? "probe_memories" : "chat_with_memories"}`
    );
    url.searchParams.set("query", query);
    const res = await fetch(url);

    if (!res.ok) {
      throw new Error(`Response not ok: ${res.status}`);
    }

    return new NextResponse(res.body);
  } catch (error) {
    console.error("Failed to probe memories:", error);
    return NextResponse.json(
      { error: "Failed to probe memories" },
      { status: 500 }
    );
  }
}
