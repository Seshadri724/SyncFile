import type { 
  InventoryStatus, 
  SetViewResponse, 
  DryRunResponse, 
  ActionResponse, 
  UnifiedFileRow 
} from "../types";

const API_BASE = "http://localhost:8000";

function getHeaders() {
  const token = localStorage.getItem("setsync_token") || "";
  return {
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export async function testConnection(token: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/inventory/status`, {
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      }
    });
    return res.status !== 401;
  } catch (e) {
    return false;
  }
}

export async function getInventoryStatus(): Promise<InventoryStatus> {
  const res = await fetch(`${API_BASE}/inventory/status`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to load inventory status");
  return res.json();
}

export async function getSetsView(
  type: string = "union",
  q?: string,
  minSize?: number,
  maxSize?: number
): Promise<SetViewResponse> {
  let url = `${API_BASE}/sets/view?type=${type}`;
  if (q) url += `&q=${encodeURIComponent(q)}`;
  if (minSize !== undefined) url += `&min_size=${minSize}`;
  if (maxSize !== undefined) url += `&max_size=${maxSize}`;
  
  const res = await fetch(url, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to load set views");
  return res.json();
}

export async function triggerRecompute(): Promise<any> {
  const res = await fetch(`${API_BASE}/sets/compute`, {
    method: "POST",
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Failed to trigger recompute");
  return res.json();
}

export async function dryRunAction(
  filePath: string,
  source: "A" | "B",
  destination: "A" | "B",
  actionType: "copy" | "move"
): Promise<DryRunResponse> {
  const res = await fetch(`${API_BASE}/actions/dry-run?action_type=${actionType}`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ file_path: filePath, source, destination }),
  });
  if (!res.ok) throw new Error("Dry-run failed");
  return res.json();
}

export async function executeCopy(
  filePath: string,
  source: "A" | "B",
  destination: "A" | "B"
): Promise<ActionResponse> {
  const res = await fetch(`${API_BASE}/actions/copy`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ file_path: filePath, source, destination }),
  });
  if (!res.ok) throw new Error("Copy execution failed");
  return res.json();
}

export async function executeMove(
  filePath: string,
  source: "A" | "B",
  destination: "A" | "B"
): Promise<ActionResponse> {
  const res = await fetch(`${API_BASE}/actions/move`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ file_path: filePath, source, destination }),
  });
  if (!res.ok) throw new Error("Move execution failed");
  return res.json();
}

export async function undoAction(actionId: string): Promise<ActionResponse> {
  const res = await fetch(`${API_BASE}/actions/${actionId}/undo`, {
    method: "POST",
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Undo execution failed");
  return res.json();
}

export async function getAuditLogs(limit: number = 100, offset: number = 0): Promise<{ actions: ActionResponse[], total_count: number }> {
  const res = await fetch(`${API_BASE}/audit-log?limit=${limit}&offset=${offset}`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to load audit logs");
  return res.json();
}
