import { useEffect, useState } from "react";
import { checkHealth } from "../api/client";

type BadgeState = "idle" | "ok" | "degraded" | "err";

function pillClass(state: BadgeState): string {
  if (state === "idle") return "pill";
  return `pill show ${state === "degraded" ? "warn" : state}`;
}

function pillText(state: BadgeState): string {
  switch (state) {
    case "ok":
      return "ok";
    case "degraded":
      return "degraded";
    case "err":
      return "unreachable";
    case "idle":
      return "";
  }
}

export function HealthBadge(): JSX.Element {
  const [state, setState] = useState<BadgeState>("idle");

  useEffect(() => {
    let cancelled = false;
    checkHealth()
      .then((res) => {
        if (cancelled) return;
        setState(res.status === "ok" ? "ok" : "degraded");
      })
      .catch(() => {
        if (cancelled) return;
        setState("err");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <span className={pillClass(state)} aria-live="polite">
      <span className="dot" />
      <span>{pillText(state)}</span>
    </span>
  );
}
