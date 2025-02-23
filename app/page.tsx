import { Suspense } from "react";
import type { Memory } from "@/app/types";
import { MemoryCard } from "@/app/components/memory-card";
import { ClientWrapper } from "@/app/components/client-wrapper";

export default async function Home({
  searchParams
}: {
  searchParams: { search?: string };
}) {
  const search = searchParams.search || "";

  return (
    <div className="min-h-screen bg-background font-sans">
      <ClientWrapper initialSearch={search} />
      <main className="container mx-auto px-4 py-8">
        <Suspense fallback={<p className="text-xl text-center">Loading memories...</p>}>
          <MemoryList search={search} />
        </Suspense>
      </main>
    </div>
  );
}

async function MemoryList({ search }: { search?: string }) {
  let data: Memory[] = [];
  let error: string | null = null;

  try {
    const response = await fetch(
      `localhost:3000/api/memories${search ? `?search=${encodeURIComponent(search)}` : ""}`,
      { cache: "no-store" }
    );
    if (!response.ok) {
      throw new Error("Failed to fetch data from the API.");
    }
    const result = await response.json();
    data = result.memories;
  } catch (e) {
    error = e instanceof Error ? e.message : `${e}`;
  }

  if (error) {
    return <p className="text-xl text-center text-red-500">{error}</p>;
  }

  if (data.length === 0) {
    return <p className="text-xl text-center">No memories found.</p>;
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
      {data.map((memory) => (
        <MemoryCard key={memory.id} memory={memory} />
      ))}
    </div>
  );
}
