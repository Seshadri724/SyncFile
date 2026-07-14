import { 
  LayoutDashboard, 
  Trash2, 
  Calendar, 
  History, 
  FileCode 
} from "lucide-react";

interface SidebarProps {
  activeTab: "dashboard" | "audit" | "dedupe" | "stale" | "plans";
  setActiveTab: (tab: "dashboard" | "audit" | "dedupe" | "stale" | "plans") => void;
  sourcesCount: number;
  fetchFiles: () => void;
  fetchDuplicates: () => void;
  fetchStaleOrphans: () => void;
  fetchLogs: () => void;
  fetchPlansList: () => void;
}

export default function Sidebar({
  activeTab,
  setActiveTab,
  sourcesCount,
  fetchFiles,
  fetchDuplicates,
  fetchStaleOrphans,
  fetchLogs,
  fetchPlansList
}: SidebarProps) {
  return (
    <div className="workspace-nav">
      <div className="workspace-tabs" role="tablist" aria-label="Workspace views">
        <button 
          className={`btn ${activeTab === "dashboard" ? "btn-primary" : ""}`}
          onClick={() => { setActiveTab("dashboard"); fetchFiles(); }}
        >
          <LayoutDashboard size={18} />
          Dashboard
        </button>
        <button 
          className={`btn ${activeTab === "dedupe" ? "btn-primary" : ""}`}
          onClick={() => { setActiveTab("dedupe"); fetchDuplicates(); }}
        >
          <Trash2 size={18} />
          Duplicates
        </button>
        <button 
          className={`btn ${activeTab === "stale" ? "btn-primary" : ""}`}
          onClick={() => { setActiveTab("stale"); fetchStaleOrphans(); }}
        >
          <Calendar size={18} />
          Stale Orphans
        </button>
        <button 
          className={`btn ${activeTab === "audit" ? "btn-primary" : ""}`}
          onClick={() => { setActiveTab("audit"); fetchLogs(); }}
        >
          <History size={18} />
          Audit Log
        </button>
        <button 
          className={`btn ${activeTab === "plans" ? "btn-primary" : ""}`}
          onClick={() => { setActiveTab("plans"); fetchPlansList(); }}
        >
          <FileCode size={18} />
          Transaction Plans
        </button>
      </div>
      
      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
        Active Devices Registered: <strong style={{ color: "var(--text-secondary)" }}>{sourcesCount}</strong>
      </div>
    </div>
  );
}
