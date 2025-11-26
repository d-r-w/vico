
import { NextResponse } from "next/server";
import { INFERENCE_API_URL } from "@/app/api/config";

const getJSONRequest = (method: string, bodyJSON?: string) => {
  const options: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
  };
  if (bodyJSON) options.body = bodyJSON;
  return options;
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await fetch(`${INFERENCE_API_URL}tags/`, getJSONRequest('POST', JSON.stringify(body)));
    
    if (!response.ok) {
        const text = await response.text();
        throw new Error(`Backend error: ${text}`);
    }
    
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to create tag", error);
    return NextResponse.json({ success: false, error: "Failed to create tag" }, { status: 500 });
  }
}

export async function GET() {
  try {
    const response = await fetch(`${INFERENCE_API_URL}tags/`, getJSONRequest('GET'));
    if (!response.ok) throw new Error(`Backend error: ${response.status}`);
    
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to fetch tags", error);
    return NextResponse.json({ tags: [] }, { status: 500 });
  }
}
