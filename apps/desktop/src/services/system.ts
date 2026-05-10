import { sendRequest } from "./jsonrpc";
import type { SystemStatus, DependenciesCheck } from "../types";

export async function fetchSystemStatus(): Promise<{
  status: SystemStatus | null;
  deps: DependenciesCheck | null;
}> {
  let status: SystemStatus | null = null;
  let deps: DependenciesCheck | null = null;

  try {
    status = await sendRequest("system.get_status", {});
  } catch (e) {
    console.error("[fetchSystemStatus] get_status failed:", e);
  }

  try {
    deps = await sendRequest("system.check_dependencies", {});
  } catch (e) {
    console.error("[fetchSystemStatus] check_dependencies failed:", e);
  }

  return { status, deps };
}
