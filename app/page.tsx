"use client";

import { useState, useEffect } from "react";
import type { Greeting } from "@/app/types";

export default function Home() {
  const [data, setData] = useState<Greeting[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/hello")
      .then((response) => response.json())
      .then((result) => setData(result.data))
      .catch((error) => {
        console.error("Error fetching API:", error);
        setError("Failed to fetch data from the API.");
      });
  }, []);

  return (
    <div className="grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20 font-[family-name:var(--font-geist-sans)]">
      <main className="flex flex-col gap-8 row-start-2 items-center sm:items-start">
        <h1 className="text-4xl font-bold">Application</h1>
        {error ? (
          <p className="text-red-500">{error}</p>
        ) : data ? (
          <>
            <p className="text-xl">Data from API:</p>
            <code>{JSON.stringify(data, null, 2)}</code>
          </>
        ) : (
          <p>Loading...</p>
        )}
      </main>
    </div>
  );
}
