import { Suspense } from "react";
import type { Memory, Tag } from "@/app/types";
import { MemoryCard } from "@/app/components/memory-card";
import { Footer } from "@/app/components/footer";
import { SidebarLayout } from "@/app/components/sidebar-layout";
import { ScrollArea } from "@/components/ui/scroll-area";
import { VICO_API_URL } from "@/app/api/config";

interface HomeProps {
  searchParams: { search?: string; tag?: string };
}

async function getTags(): Promise<Tag[]> {
  try {
    const res = await fetch(`${VICO_API_URL}tags`, { cache: 'no-store' });
    if (!res.ok) return [];
    const data = await res.json();
    return data.tags;
  } catch (e) {
    return [];
  }
}

export default async function Home({ searchParams }: HomeProps) {
  const search = searchParams.search ?? "";
  const tag = searchParams.tag;
  const tags = await getTags();

  return (
    <div className="h-screen flex flex-col bg-background font-mono">
      <SidebarLayout tags={tags} initialSearch={search}>
        <ScrollArea className="h-full pr-2.5">
          <main className="container mx-auto px-2 py-4">
            <Suspense fallback={<p className="text-xl text-center">Loading memories...</p>}>
              <MemoryList search={search} tag={tag} />
            </Suspense>
          </main>
          <Footer />
        </ScrollArea>
      </SidebarLayout>
    </div>
  );
}

async function MemoryList({ search, tag }: { search?: string; tag?: string }) {
  let data: Memory[] = [];
  let error: string | null = null;

  try {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (tag) params.set("tag", tag);

    const response = await fetch(
      `${VICO_API_URL}memories?${params.toString()}`,
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
    <div className="flex justify-center">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 w-full sm:w-auto max-w-md sm:max-w-none">
        {data.map((memory) => (
          <MemoryCard key={memory.id} memory={memory} />
        ))}
      </div>
    </div>
  );
}
