import { Database } from "duckdb-async";
import { NextResponse } from "next/server";

const DUCKDB_IN_MEMORY_DATABASE_PATH = ":memory:";

export async function GET() {
  try {
    const db = await Database.create(DUCKDB_IN_MEMORY_DATABASE_PATH);

    await db.run("CREATE TABLE greetings (id INTEGER, message TEXT)");
    await db.run(
      "INSERT INTO greetings VALUES (1, 'Hello, World!'), (2, 'Hi, DuckDB!')"
    );

    const rows = await db.all("SELECT * FROM greetings");

    await db.close();

    return NextResponse.json({ data: rows });
  } catch (error) {
    console.error("Database error:", error);
    return NextResponse.json(
      { error: "Failed to query the database." },
      { status: 500 }
    );
  }
}
