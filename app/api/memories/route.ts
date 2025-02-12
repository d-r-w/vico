import { Database } from "duckdb-async";
import { NextResponse } from "next/server";
import fs from "node:fs/promises";
import path from "node:path";

const DATA_DIR = path.join(process.cwd(), "data");
const DUCKDB_PERSISTENT_DATABASE_PATH = path.join(DATA_DIR, "database.db");

async function ensureDataDirectoryExists() {
  try {
    await fs.access(DATA_DIR);
  } catch (error) {
    console.debug(error);
    await fs.mkdir(DATA_DIR, { recursive: true });
  }
}

async function ensureMemoriesTableExists(db: Database): Promise<void> {
  await db.run(`
    CREATE TABLE IF NOT EXISTS memories (
      memory TEXT,
      media TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
  `);
}

interface Memory {
  memory: string;
  media?: string;
  created_at: string;
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const searchTerm = searchParams.get("search");

    await ensureDataDirectoryExists();
    const db = await Database.create(DUCKDB_PERSISTENT_DATABASE_PATH);
    await ensureMemoriesTableExists(db);

    let rows: Memory[];
    if (searchTerm && searchTerm.trim() !== "") {
      console.debug(`Searching for \`${searchTerm}\``);
      rows = (await db.all(
        "SELECT memory, media, created_at FROM memories WHERE memory ILIKE ? ORDER BY created_at DESC",
        [`%${searchTerm}%`]
      )) as Memory[];
    } else {
      console.debug("Not searching.");
      rows = (await db.all(
        "SELECT memory, created_at FROM memories ORDER BY created_at DESC LIMIT 5"
      )) as Memory[];
    }

    await db.close();
    return NextResponse.json({ memories: rows });
  } catch (error) {
    console.error("Database error in GET:", error);
    return NextResponse.json(
      { error: "Failed to fetch memories." },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const memoryText: string = body.memory;
    const media: string | undefined = body.media;

    console.debug(body);

    await ensureDataDirectoryExists();
    const db = await Database.create(DUCKDB_PERSISTENT_DATABASE_PATH);
    await ensureMemoriesTableExists(db);

    if (media && typeof media === "string") {
      console.debug(media);
      try {
        const extractUrl = "http://192.168.0.99:8000/extract_text_base64/";
        const response = await fetch(extractUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ base64_image: media })
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // TODO Modify ocr_service to provide text and a detailed explanation
        const extractedMemoryText = `${data.extracted_text}\n\n${data.image_description}`;

        console.debug(data);

        await db.run("INSERT INTO memories (memory, media) VALUES (?, ?);", [
          extractedMemoryText,
          media
        ]);
      } catch (error) {
        console.error("Error extracting text from media:", error);

        // TODO If there's an error, simply store the media
        await db.run("INSERT INTO memories (media) VALUES (?);", [media]);
      }
    } else {
      await db.run("INSERT INTO memories (memory) VALUES (?);", [memoryText]);
    }

    await db.close();

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Database error in POST:", error);
    return NextResponse.json(
      { error: "Failed to store memory." },
      { status: 500 }
    );
  }
}
