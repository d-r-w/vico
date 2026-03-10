import { NextResponse } from "next/server";
import { INFERENCE_API_URL } from "@/app/api/config";

export async function POST() {
  try {
    const res = await fetch(`${INFERENCE_API_URL}agent/reset/`, {
      method: "POST",
    });

    if (!res.ok) {
      throw new Error(`Response not ok: ${res.status}`);
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Failed to reset agent cache:", error);
    return NextResponse.json(
      { error: "Failed to reset agent cache" },
      { status: 500 },
    );
  }
}
