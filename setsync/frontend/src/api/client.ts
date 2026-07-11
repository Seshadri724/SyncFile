import type { 
  InventoryStatus, 
  SetViewResponse, 
  DryRunResponse, 
  ActionResponse 
} from "../types";

// Vite serves the development UI on a different port than the API and the
// production Docker image on the same origin.  Keeping this configurable
// avoids shipping a hard-coded localhost integration.
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

async function getErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return body.detail || body.message || fallback;
  } catch {
    return fallback;
  }
}

async function request(path: string, init: RequestInit = {}, fallback = "Request failed"): Promise<Response> {
  let res: Response;
  try {
    const mergedInit = { ...init, credentials: init.credentials || "include" as const };
    res = await fetch(`${API_BASE}${path}`, mergedInit);
  } catch {
    throw new Error("Cannot reach SetSync. Check that the API service is running.");
  }
  if (!res.ok) throw new Error(await getErrorMessage(res, fallback));
  return res;
}

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
    return res.ok;
  } catch {
    return false;
  }
}

export async function getInventoryStatus(): Promise<InventoryStatus> {
  const res = await request("/inventory/status", { headers: getHeaders() }, "Failed to load inventory status");
  return res.json();
}

export async function getSources(): Promise<any[]> {
  const res = await request("/sources", { headers: getHeaders() }, "Failed to load sources");
  return res.json();
}

export async function getSetsView(
  sourceX: string,
  sourceY: string,
  type: string = "union",
  q?: string,
  minSize?: number,
  maxSize?: number
): Promise<SetViewResponse> {
  let url = `/sets/view?source_x=${encodeURIComponent(sourceX)}&source_y=${encodeURIComponent(sourceY)}&type=${encodeURIComponent(type)}`;
  if (q) url += `&q=${encodeURIComponent(q)}`;
  if (minSize !== undefined) url += `&min_size=${minSize}`;
  if (maxSize !== undefined) url += `&max_size=${maxSize}`;
  
  const res = await request(url, { headers: getHeaders() }, "Failed to load set views");
  return res.json();
}

export async function triggerRecompute(sourceX: string, sourceY: string): Promise<any> {
  const res = await request(`/sets/compute?source_x=${encodeURIComponent(sourceX)}&source_y=${encodeURIComponent(sourceY)}`, {
    method: "POST",
    headers: getHeaders(),
  });
  return res.json();
}

export async function dryRunAction(
  filePath: string,
  source: string,
  destination: string,
  actionType: "copy" | "move"
): Promise<DryRunResponse> {
  const res = await request(`/actions/dry-run?action_type=${actionType}`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ file_path: filePath, source, destination }),
  });
  return res.json();
}

export async function executeCopy(
  filePath: string,
  source: string,
  destination: string
): Promise<ActionResponse> {
  const res = await request("/actions/copy", {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ file_path: filePath, source, destination }),
  });
  return res.json();
}

export async function executeMove(
  filePath: string,
  source: string,
  destination: string
): Promise<ActionResponse> {
  const res = await request("/actions/move", {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ file_path: filePath, source, destination }),
  });
  return res.json();
}

export async function executeDelete(
  filePath: string,
  source: string,
  force: boolean = false
): Promise<ActionResponse> {
  const res = await request(`/actions/delete?force=${force}`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ file_path: filePath, source, destination: source }),
  });
  return res.json();
}

export async function undoAction(actionId: string): Promise<ActionResponse> {
  const res = await request(`/actions/${encodeURIComponent(actionId)}/undo`, {
    method: "POST",
    headers: getHeaders(),
  });
  return res.json();
}

export async function getAuditLogs(limit: number = 100, offset: number = 0): Promise<{ actions: ActionResponse[], total_count: number }> {
  const res = await request(`/audit-log?limit=${limit}&offset=${offset}`, { headers: getHeaders() }, "Failed to load audit logs");
  return res.json();
}

export async function getDuplicates(): Promise<any> {
  const res = await request("/analysis/duplicates", { headers: getHeaders() }, "Failed to load duplicates report");
  return res.json();
}

export async function getStaleOrphans(ageDays: number = 180): Promise<any> {
  const res = await request(`/analysis/stale-orphans?age_days=${ageDays}`, { headers: getHeaders() }, "Failed to load stale orphans report");
  return res.json();
}

export async function queryNaturalLanguage(
  prompt: string,
  sourceX: string,
  sourceY: string
): Promise<any> {
  const res = await request("/query/natural", {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ prompt, source_x: sourceX, source_y: sourceY }),
  });
  return res.json();
}

// Plan Management
export async function createPlan(name: string, items: any[]): Promise<any> {
  const res = await request("/plans", {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ name, items }),
  });
  return res.json();
}

export async function getPlans(): Promise<any[]> {
  const res = await request("/plans", { headers: getHeaders() }, "Failed to fetch plans");
  return res.json();
}

export async function getPlan(id: string): Promise<any> {
  const res = await request(`/plans/${encodeURIComponent(id)}`, { headers: getHeaders() }, "Failed to fetch plan details");
  return res.json();
}

export async function approvePlan(id: string): Promise<any> {
  const res = await request(`/plans/${encodeURIComponent(id)}/approve`, {
    method: "POST",
    headers: getHeaders(),
  });
  return res.json();
}

export async function undoPlan(id: string): Promise<any> {
  const res = await request(`/plans/${encodeURIComponent(id)}/undo`, {
    method: "POST",
    headers: getHeaders(),
  });
  return res.json();
}

// Conflict Analysis
export async function analyzeConflict(
  filePath: string,
  sourceX: string,
  sourceY: string,
  metadataX: any,
  metadataY: any
): Promise<{ recommendation: string; reasoning: string }> {
  const res = await request("/query/analyze-conflict", {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({
      file_path: filePath,
      source_x: sourceX,
      source_y: sourceY,
      metadata_x: metadataX,
      metadata_y: metadataY,
    }),
  });
  return res.json();
}

// Semantic duplicates
export async function getSemanticDuplicates(threshold: number = 10): Promise<any[]> {
  const res = await request(`/analysis/semantic-duplicates?threshold=${threshold}`, {
    headers: getHeaders(),
  });
  return res.json();
}

// Enterprise Auth, Fleet, and Governance APIs
export async function loginUser(email: string, password: string): Promise<any> {
  const res = await request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return res.json();
}

export async function registerOrganization(name: string): Promise<any> {
  const res = await request("/auth/organizations", {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ name }),
  });
  return res.json();
}

export async function registerUser(email: string, password: string, role: string, orgId: string): Promise<any> {
  const res = await request("/auth/users", {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ email, password, role, org_id: orgId }),
  });
  return res.json();
}

export async function getFleetStats(): Promise<any> {
  const res = await request("/analysis/fleet", {
    headers: getHeaders(),
  }, "Failed to fetch fleet statistics");
  return res.json();
}

export async function decommissionSource(id: string): Promise<any> {
  const res = await request(`/sources/${encodeURIComponent(id)}/decommission`, {
    method: "POST",
    headers: getHeaders(),
  });
  return res.json();
}

export async function logoutUser(): Promise<any> {
  const res = await request("/auth/logout", {
    method: "POST",
    headers: getHeaders(),
  });
  localStorage.removeItem("setsync_token");
  return res.json();
}
