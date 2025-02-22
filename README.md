## Vico
Vico is a Vision Memory Copilot - a modern web application that helps you store, manage, and search through memories with advanced visual capabilities. It combines powerful image processing with text-based memory storage, offering an intuitive interface for managing your digital memories.

### Features
- Visual Memory Storage: Upload and store images with automatic detailed descriptions
- Text Memory Management: Create, edit, and delete text-based memories
- Advanced Search: Search through your memories with natural language queries
- Real-time Updates: Instant feedback for all memory operations
- Responsive Design: Mobile-first interface that works across all devices

### Technology Stack
- Frontend: Next.js 14 with App Router, React, and TypeScript
- Styling: Tailwind CSS with shadcn/ui components
- Database: DuckDB for efficient memory storage
- ML Integration: Advanced vision-language models for image processing
- Runtime: Bun.sh for enhanced JavaScript/TypeScript execution

### Architecture
- Server Components: Optimized for performance with React Server Components
- API Routes: RESTful endpoints for memory management
- CORS Support: Configured for Chrome extension integration
- Type Safety: Full TypeScript implementation throughout the codebase

## To Use
The environment is used as expected with [an installation of Bun.sh](https://bun.sh/docs/installation):

bun install

bun run dev

bun run build