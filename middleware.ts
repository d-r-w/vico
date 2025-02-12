import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  // Handle OPTIONS requests (preflight)
  if (request.method === "OPTIONS") {
    return new NextResponse(null, {
      headers: {
        "Access-Control-Allow-Origin":
          "chrome-extension://hhbkeeppcfngbcplcneanmkecehbkeni",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "86400"
      }
    });
  }

  // For all other requests, clone the response and add CORS headers
  const response = NextResponse.next();
  response.headers.set(
    "Access-Control-Allow-Origin",
    "chrome-extension://hhbkeeppcfngbcplcneanmkecehbkeni"
  );
  response.headers.set(
    "Access-Control-Allow-Methods",
    "GET, POST, PUT, DELETE, OPTIONS"
  );
  response.headers.set(
    "Access-Control-Allow-Headers",
    "Content-Type, Authorization"
  );
  response.headers.set("Access-Control-Max-Age", "86400");
  return response;
}

// Apply the middleware to all API routes
export const config = {
  matcher: "/api/:path*"
};
