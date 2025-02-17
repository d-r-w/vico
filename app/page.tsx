import type { Memory } from "@/app/types";
import { MemoryCard } from "@/app/components/memory-card";

export default async function Home() {
  async function getMemories(): Promise<Memory[]> {
    const response = await fetch("http://localhost:3000/api/memories", {
      cache: "no-store"
    });
    if (!response.ok) {
      throw new Error("Failed to fetch data from the API.");
    }
    const result = await response.json();
    return result.memories;
  }

  let error = null;
  let data: Memory[] = [];

  try {
    data = await getMemories();
  } catch (e: unknown) {
    error = e instanceof Error ? e.message : `${e}`;
  }

  return (
    <div className="min-h-screen p-4 pb-10 sm:p-10 font-[family-name:var(--font-geist-sans)]">
      <main className="max-w-7xl mx-auto">
        {error ? (
          <p className="text-red-500">{error}</p>
        ) : data.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.map((memory) => (
              <MemoryCard key={memory.id} memory={memory} />
            ))}
          </div>
        ) : (
          <p className="text-xl text-center">No memories found.</p>
        )}
      </main>
    </div>
  );
}
