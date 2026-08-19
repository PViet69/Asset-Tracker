type AppConfig = {
  readonly apiBase: string;
  readonly apiKey?: string;
};

function readEnv(key: string): string | undefined {
  const value = import.meta.env[key];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

// Empty apiBase = same-origin requests ("/v1/..."). The backend serves no
// CORS headers, so same-origin behind the Vite dev proxy or the Docker
// nginx proxy is the supported layout. Set VITE_API_BASE only when the
// backend gains CORS support.
export const config: AppConfig = Object.freeze({
  apiBase: readEnv("VITE_API_BASE") ?? "",
  apiKey: readEnv("VITE_API_KEY"),
});
