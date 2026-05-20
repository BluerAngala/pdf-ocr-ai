import type { ModuleTaskUiState, ModuleType } from "./types";
import { ALL_MODULE_TYPES } from "./constants";

export function createDefaultModuleTaskState(): ModuleTaskUiState {
  return {
    previewState: "empty",
    phase: "",
    progressCurrent: 0,
    progressTotal: 0,
    progressFileCurrent: 0,
    progressFileTotal: 0,
    progressMessage: "",
    result: null,
    running: false,
    cancelling: false,
    taskId: null,
    liveCompanies: [],
  };
}

export function createInitialModuleTaskState(): Record<ModuleType, ModuleTaskUiState> {
  return Object.fromEntries(
    ALL_MODULE_TYPES.map((m) => [m, createDefaultModuleTaskState()]),
  ) as Record<ModuleType, ModuleTaskUiState>;
}

export function resolveTaskModule(
  taskId: string,
  taskIdToModule: Record<string, ModuleType>,
): ModuleType | undefined {
  const mapped = taskIdToModule[taskId];
  if (mapped) return mapped;
  for (const m of ALL_MODULE_TYPES) {
    if (taskId.startsWith(`${m}-`)) return m;
  }
  if (taskId.startsWith("preview-")) return "print";
  return undefined;
}
