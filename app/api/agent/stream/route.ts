import { NextResponse } from "next/server";
import type { IncomingMessage } from "node:http";
import { request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { INFERENCE_API_URL } from "@/app/api/config";

export const runtime = "nodejs";

const getRequestClient = (protocol: string) => {
  return protocol === "https:" ? httpsRequest : httpRequest;
};

const readResponseText = async (response: IncomingMessage): Promise<string> => {
  const chunks: Uint8Array[] = [];

  for await (const chunk of response) {
    if (typeof chunk === "string") {
      chunks.push(Buffer.from(chunk));
      continue;
    }
    chunks.push(chunk);
  }

  return Buffer.concat(chunks).toString("utf8");
};

const requestStream = (url: URL, signal: AbortSignal): Promise<IncomingMessage> => {
  const requestClient = getRequestClient(url.protocol);

  return new Promise((resolve, reject) => {
    const upstreamRequest = requestClient(url, { method: "GET" }, resolve);

    const abortRequest = () => {
      upstreamRequest.destroy(new Error("Client aborted request"));
    };

    upstreamRequest.on("error", reject);

    if (signal.aborted) {
      abortRequest();
      return;
    }

    signal.addEventListener("abort", abortRequest, { once: true });
    upstreamRequest.end();
  });
};

export async function POST(request: Request) {
  try {
    const body: { query?: unknown } = await request.json();
    const query = typeof body.query === "string" ? body.query.trim() : "";

    if (!query) {
      return NextResponse.json({ error: "Query is required" }, { status: 400 });
    }

    const url = new URL(`${INFERENCE_API_URL}agent/stream/`);
    url.searchParams.set("query", query);

    const res = await requestStream(url, request.signal);
    const status = res.statusCode ?? 500;

    if (status < 200 || status >= 300) {
      const errorBody = await readResponseText(res);
      throw new Error(`Response not ok: ${status}${errorBody ? ` ${errorBody}` : ""}`);
    }

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        res.on("data", (chunk: Buffer | string) => {
          controller.enqueue(typeof chunk === "string" ? Buffer.from(chunk) : chunk);
        });
        res.on("end", () => controller.close());
        res.on("error", error => controller.error(error));
      },
      cancel() {
        res.destroy();
      },
    });

    return new NextResponse(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
      status,
    });
  } catch (error) {
    console.error("Failed to stream agent response:", error);
    return NextResponse.json(
      { error: "Failed to stream agent response" },
      { status: 500 }
    );
  }
}
