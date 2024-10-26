import type { Greeting } from "@/app/types";

export default async function Home() {
  async function getGreetings(): Promise<Greeting[]> {
    const response = await fetch("http://localhost:3000/api/hello", {
      cache: "no-store"
    });
    if (!response.ok) {
      throw new Error("Failed to fetch data from the API.");
    }
    const result = await response.json();
    return result.data;
  }

  let error = null;
  let data: Greeting[] = [];

  try {
    data = await getGreetings();
  } catch (e: unknown) {
    error = e instanceof Error ? e.message : `${e}`;
  }

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
