
import { useEffect, useState } from "react";
import { apiClient } from "../services/apiClient";

export type BackendStatus = "checking" | "online" | "offline";

interface HealthResponse {
  status: string;
  application: string;
  version: string;
}

export function useBackendHealth() {
  const [backendStatus, setBackendStatus] =
    useState<BackendStatus>("checking");

  useEffect(() => {
    let active = true;

    async function checkHealth() {
      try {
        const result =
          await apiClient.get<HealthResponse>("/api/health");

        if (active) {
          setBackendStatus(
            result.status === "healthy" ? "online" : "offline",
          );
        }
      } catch {
        if (active) {
          setBackendStatus("offline");
        }
      }
    }

    void checkHealth();

    return () => {
      active = false;
    };
  }, []);

  return backendStatus;
}
