import type { Memory } from "@/app/types";
import { NextResponse } from "next/server";
import { INFERENCE_API_URL } from "@/app/api/config";

async function fetchMemories(url: URL): Promise<Memory[]> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const data: { memories: [number, string, string | null, string][] } =
    await response.json();

  return data.memories.map(([id, memory, image, created_at]) => ({
    id,
    memory,
    image,
    created_at
  }));
}

const getJSONRequest = (method: string, bodyJSON: string) => {
  return {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
    body: bodyJSON
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const search = searchParams.get("search");

    if (search) {
      const url = new URL(`${INFERENCE_API_URL}search_memories/`);
      url.searchParams.set("search", search);

      const memories = await fetchMemories(url);
      return NextResponse.json({ memories });
    }

    const url = new URL(`${INFERENCE_API_URL}recent_memories/`);
    url.searchParams.set("limit", "50");

    const memories = await fetchMemories(url);
    return NextResponse.json({ memories });
  } catch (error) {
    console.error("Failed to fetch memories", error);
    return NextResponse.json(
      { error: "Failed to fetch memories" },
      { status: 500 }
    );
  }
}

export async function DELETE(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get("id");

    if (!id) {
      throw new Error("`id` is required");
    }

    const response = await fetch(
      `${INFERENCE_API_URL}delete_memory/`,
      getJSONRequest('DELETE', JSON.stringify({ memory_id: id }))
    );
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Failed to delete memory", error);
    return NextResponse.json(
      { success: false, error: "Failed to delete memory" },
      { status: 500 }
    );
  }
}

export async function PATCH(request: Request) {
  try {
    const body = await request.json();
    const { id, memory } = body;

    if (!id || !memory) {
      throw new Error("Both `id` and `memory` are required");
    }

    const response = await fetch(`${INFERENCE_API_URL}edit_memory/`, getJSONRequest('PATCH', JSON.stringify({ id, memory })));

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Failed to edit memory", error);
    return NextResponse.json(
      { success: false, error: "Failed to edit memory" },
      { status: 500 }
    );
  }
}
