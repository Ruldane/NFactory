import type { ProjectType } from "@/lib/api/types";

// Short labels for the filter chips. The full list of types, with their phase, comes
// from GET /recipes (see the New project page); unknown types show their raw name.
export const PROJECT_TYPE_LABELS: Record<string, string> = {
  api: "API",
  excel: "Excel",
  document: "Document",
  webapp: "Web app",
  powershell: "PowerShell",
  feature: "Repo existant",
};

export const PROJECT_TYPES = Object.keys(PROJECT_TYPE_LABELS) as ProjectType[];

export function projectTypeLabel(type: ProjectType): string {
  return PROJECT_TYPE_LABELS[type] ?? type;
}
