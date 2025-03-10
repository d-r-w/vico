import { Suspense } from "react";
import type { Memory } from "@/app/types";
import { MemoryCard } from "@/app/components/memory-card";
import { ClientWrapper } from "@/app/components/client-wrapper";
import { Footer } from "@/app/components/footer";
import { ScrollArea } from "@/components/ui/scroll-area";
import { VICO_API_URL } from "@/app/api/config";
import { 
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle 
} from "@/components/ui/resizable";

interface HomeProps {
  searchParams: { search?: string };
}

export default async function Home({ searchParams }: HomeProps) {
  const search = searchParams.search ?? "";

  return (
    <div className="h-screen flex flex-col bg-background font-mono">
      <ResizablePanelGroup direction="vertical" className="flex-1">
        <ResizablePanel defaultSize={40} minSize={25}>
          <ClientWrapper initialSearch={search} />
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={60}>
          <ScrollArea className="h-full pr-2.5">
            <main className="container mx-auto px-2 py-4">
              <Suspense fallback={<p className="text-xl text-center">Loading memories...</p>}>
                <MemoryList search={search} />
              </Suspense>
            </main>
            <Footer />
          </ScrollArea>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}

async function MemoryList({ search }: { search?: string }) {
  let data: Memory[] = [];
  let error: string | null = null;

  try {
    const response = await fetch(
      `${VICO_API_URL}memories${search ? `?search=${encodeURIComponent(search)}` : ""}`,
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
