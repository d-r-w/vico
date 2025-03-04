import { Fragment } from "react";
import Image from "next/image";

type Badge = {
  websiteUrl: string;
  iconSrc: string;
  altText: string;
};

const badges: Badge[] = [
  {
    websiteUrl: "https://bun.sh/",
    iconSrc: "https://bun.sh/logo_avatar.svg",
    altText: "Bun.sh logo"
  },
  {
    websiteUrl: "https://ui.shadcn.com/",
    iconSrc: "https://ui.shadcn.com/favicon.ico",
    altText: "shadcn logo"
  },
  {
    websiteUrl: "https://nextjs.org/",
    iconSrc: "https://nextjs.org/favicon.ico",
    altText: "Next.js logo"
  },
  {
    websiteUrl: "https://duckdb.org/",
    iconSrc: "https://duckdb.org/images/favicon/favicon-32x32.png",
    altText: "DuckDB logo"
  }
];

export function Footer() {
  return (
    <footer className="py-2 bg-gray-100 dark:bg-gray-800">
      <div className="container mx-auto flex justify-center items-center gap-4 flex-wrap">
        {badges.map((badge, index) => (
          <Fragment key={badge.websiteUrl}>
            {index > 0 && "+"}
            <a
              className="flex items-center gap-2 hover:underline hover:underline-offset-4 h-5"
              href={badge.websiteUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Image
                className="dark:invert h-full w-auto"
                src={badge.iconSrc}
                alt={badge.altText}
                width={0}
                height={0}
                sizes="100%"
                priority
              />
            </a>
          </Fragment>
        ))}
      </div>
    </footer>
  );
}
