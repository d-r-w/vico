"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";

export default function SearchInput({
  initialSearch = ""
}: { initialSearch?: string }) {
  const [search, setSearch] = useState(initialSearch);
  const router = useRouter();

  return (
    <div className="flex gap-2">
      <Input
        type="search"
        name="search"
        autoComplete="off"
        placeholder="Search memories..."
        value={search}
        onChange={(e) => {
          const value = e.target.value;
          setSearch(value);
          router.push(`/?search=${encodeURIComponent(value)}`);
        }}
        className="flex-grow"
      />
    </div>
  );
}
