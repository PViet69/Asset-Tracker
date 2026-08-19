type AppConfig = {
  readonly apiBase: string;
  readonly apiKey?: string;
};

function readEnv(key: string): string | undefined {
  const value = import.meta.env[key];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

export const config: AppConfig = Object.freeze({
  apiBase: readEnv("VITE_API_BASE") ?? "http://localhost:8000",
  apiKey: readEnv("VITE_API_KEY"),
});
