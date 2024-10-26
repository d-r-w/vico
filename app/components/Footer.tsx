import Image from "next/image";

export default function Footer() {
  return (
    <footer className="py-4 bg-gray-100 dark:bg-gray-800">
      <div className="container mx-auto flex justify-center items-center gap-6 flex-wrap">
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4 h-5"
          href="https://bun.sh/"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            className="dark:invert h-full w-auto"
            src="https://bun.sh/logo_avatar.svg"
            alt="Bun.sh logo"
            width={0}
            height={0}
            sizes="100%"
            priority
          />
        </a>
        +
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4 h-4"
          href="https://ui.shadcn.com/"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            className="h-full w-auto"
            src="https://ui.shadcn.com/favicon.ico"
            alt="shadcn logo"
            width={0}
            height={0}
            sizes="100%"
          />
        </a>
        +
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4 h-5"
          href="https://nextjs.org/"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            className="dark:invert h-full w-auto"
            src="https://nextjs.org/icons/next.svg"
            alt="Next.js logo"
            width={0}
            height={0}
            sizes="100%"
            priority
          />
        </a>
        +
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4 h-5"
          href="https://duckdb.org/"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            className="dark:invert h-full w-auto"
            src="https://duckdb.org/images/favicon/favicon-32x32.png"
            alt="Next.js logo"
            width={0}
            height={0}
            sizes="100%"
            priority
          />
        </a>
      </div>
    </footer>
  );
}
