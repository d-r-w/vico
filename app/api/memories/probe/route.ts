import { NextResponse } from "next/server";
import { INFERENCE_API_URL } from "../../config";

async function probeMemories(query: string, isDeep: boolean): Promise<{ response: string }> {
  const response = await fetch(`${INFERENCE_API_URL}${isDeep ? "probe_memories" : "chat_with_memories"}/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    throw new Error(`Failed to probe memories: ${response.statusText}`);
  }

  return response.json();
}

export async function POST(request: Request) {
  try {
    const { query, isDeep } = await request.json();
    
    if (!query?.trim()) {
      return NextResponse.json(
        { error: "Query is required" },
        { status: 400 }
      );
    }

    const result = await probeMemories(query, isDeep);
    console.debug(result);
    return NextResponse.json(result);
  } catch (error) {
    console.error("Failed to probe memories:", error);
    return NextResponse.json(
      { error: "Failed to probe memories" },
      { status: 500 }
    );
  }
}