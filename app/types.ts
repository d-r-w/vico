export interface Memory {
  id: number;
  memory: string;
  image: string | null;
  created_at: string;
}

export const MODES = {
  SEARCH: "search",
  CHAT: "chat",
} as const;

export type Mode = typeof MODES[keyof typeof MODES];
