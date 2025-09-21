"use client"

interface ToolCall {
  toolName: string;
  state: "loading" | "ready" | "error" | "default";
  input?: unknown;
  output?: unknown;
}

interface ToolCallRendererProps {
  toolCall: ToolCall;
}

export function ToolCallRenderer({ toolCall }: ToolCallRendererProps) {
  const { toolName, input, output, state } = toolCall;
  
  const getStateColor = (state: string) => {
    switch (state) {
      case "loading":
        return "border-yellow-300 dark:border-yellow-600 bg-yellow-50 dark:bg-yellow-900/20";
      case "ready":
        return "border-green-300 dark:border-green-600 bg-green-50 dark:bg-green-900/20";
      case "error":
        return "border-red-300 dark:border-red-600 bg-red-50 dark:bg-red-900/20";
      default:
        return "border-blue-300 dark:border-blue-600 bg-blue-50 dark:bg-blue-900/20";
    }
  };

  const getStateIcon = (state: string) => {
    switch (state) {
      case "loading":
        return (
          <div className="w-3 h-3 border-2 border-yellow-600 border-t-transparent rounded-full animate-spin"></div>
        );
      case "ready":
        return <div className="w-3 h-3 bg-green-600 rounded-full"></div>;
      case "error":
        return <div className="w-3 h-3 bg-red-600 rounded-full"></div>;
      default:
        return <div className="w-3 h-3 bg-blue-600 rounded-full"></div>;
    }
  };

  return (
    <div
      className={`mt-2 p-3 rounded-lg border ${getStateColor(state || "default")}`}
    >
      <div className="flex items-center gap-2 mb-2">
        {getStateIcon(state || "default")}
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {toolName}
        </span>
      </div>

      <div className="max-h-72 overflow-y-auto pr-1 space-y-2">
        {input && (
          <div className="mb-2">
            <div className="text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
              Input:
            </div>
            <div className="text-xs bg-zinc-100 dark:bg-zinc-800 p-2 rounded font-mono">
              {JSON.stringify(input, null, 2)}
            </div>
          </div>
        )}

        {output && (
          <div>
            <div className="text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
              Output:
            </div>
            <div className="text-xs bg-zinc-100 dark:bg-zinc-800 p-2 rounded font-mono">
              {typeof output === "string"
                ? output
                : JSON.stringify(output, null, 2)}
            </div>
          </div>
        )}

        {state === "loading" && !output && (
          <div className="text-xs text-zinc-500 dark:text-zinc-400 italic">
            Waiting for output...
          </div>
        )}
      </div>
    </div>
  );
}
