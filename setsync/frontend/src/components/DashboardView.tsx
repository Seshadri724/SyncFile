import { 
  Cpu, 
  Database, 
  HardDrive, 
  AlertTriangle, 
  ArrowRightLeft, 
  Sparkles, 
  CheckCircle, 
  Search, 
  FileCode,
  RefreshCw
} from "lucide-react";
import type { UnifiedFileRow, SetSummaryStrip, InventoryStatus } from "../types";

interface DashboardViewProps {
  fleetStats: any;
  sources: any[];
  sourceX: string;
  setSourceX: (id: string) => void;
  sourceY: string;
  setSourceY: (id: string) => void;
  handleDecommission: (s: any) => void;
  actionLoading: boolean;
  aiQueryText: string;
  setAiQueryText: (txt: string) => void;
  handleAiQuery: () => void;
  activeAiFilters: any;
  handleClearAiFilters: () => void;
  viewType: string;
  setViewType: (type: string) => void;
  summary: SetSummaryStrip;
  inventoryStatus: InventoryStatus | null;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  loadingFiles: boolean;
  files: UnifiedFileRow[];
  scrollTop: number;
  setScrollTop: (scroll: number) => void;
  handleOpenDryRun: (file: UnifiedFileRow, action: "copy" | "move") => void;
  addToDraftPlan: (file: UnifiedFileRow, action: "copy" | "move") => void;
  handleSafeDelete: (relPath: string, srcId: string) => void;
  setConflictModal: (modal: { open: boolean; row: UnifiedFileRow | null }) => void;
  formatSize: (bytes: number) => string;
  formatDate: (iso?: string) => string;
}

export default function DashboardView({
  fleetStats,
  sources,
  sourceX,
  setSourceX,
  sourceY,
  setSourceY,
  handleDecommission,
  actionLoading,
  aiQueryText,
  setAiQueryText,
  handleAiQuery,
  activeAiFilters,
  handleClearAiFilters,
  viewType,
  setViewType,
  summary,
  inventoryStatus,
  searchQuery,
  setSearchQuery,
  loadingFiles,
  files,
  scrollTop,
  setScrollTop,
  handleOpenDryRun,
  addToDraftPlan,
  handleSafeDelete,
  setConflictModal,
  formatSize,
  formatDate
}: DashboardViewProps) {
  const nameX = sources.find(s => s.id === sourceX)?.name || "Device A";
  const nameY = sources.find(s => s.id === sourceY)?.name || "Device B";

  return (
    <>
      {/* Fleet Dashboard Panel */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
        <div className="glass-card" style={{ padding: "1.25rem", display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ padding: "0.75rem", borderRadius: "10px", backgroundColor: "rgba(0,188,212,0.1)", color: "var(--accent-cyan)" }}>
            <Cpu size={24} />
          </div>
          <div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Fleet Status</div>
            <div style={{ fontSize: "1.5rem", fontWeight: "700" }}>
              {fleetStats ? fleetStats.total_sources : 0} <span style={{ fontSize: "0.85rem", fontWeight: "400", color: "var(--success)" }}>({fleetStats ? fleetStats.active_sources : 0} online)</span>
            </div>
          </div>
        </div>

        <div className="glass-card" style={{ padding: "1.25rem", display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ padding: "0.75rem", borderRadius: "10px", backgroundColor: "rgba(156,39,176,0.1)", color: "var(--purple)" }}>
            <Database size={24} />
          </div>
          <div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Monitored Files</div>
            <div style={{ fontSize: "1.5rem", fontWeight: "700" }}>
              {fleetStats ? fleetStats.total_files.toLocaleString() : 0}
            </div>
          </div>
        </div>

        <div className="glass-card" style={{ padding: "1.25rem", display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ padding: "0.75rem", borderRadius: "10px", backgroundColor: "rgba(0,150,136,0.1)", color: "var(--success)" }}>
            <HardDrive size={24} />
          </div>
          <div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Monitored Space</div>
            <div style={{ fontSize: "1.5rem", fontWeight: "700" }}>
              {fleetStats ? formatSize(fleetStats.total_bytes) : "0 Bytes"}
            </div>
          </div>
        </div>

        <div className="glass-card" style={{ 
          padding: "1.25rem", 
          display: "flex", 
          alignItems: "center", 
          gap: "1rem",
          border: fleetStats && fleetStats.unique_files_count > 0 ? "1px solid rgba(255,87,34,0.3)" : "1px solid transparent",
          background: fleetStats && fleetStats.unique_files_count > 0 ? "linear-gradient(135deg, rgba(255,255,255,0.01) 0%, rgba(255,87,34,0.02) 100%)" : ""
        }}>
          <div style={{ 
            padding: "0.75rem", 
            borderRadius: "10px", 
            backgroundColor: fleetStats && fleetStats.unique_files_count > 0 ? "rgba(255,87,34,0.1)" : "rgba(255,255,255,0.05)", 
            color: fleetStats && fleetStats.unique_files_count > 0 ? "#FF5722" : "var(--text-muted)" 
          }}>
            <AlertTriangle size={24} />
          </div>
          <div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Unique Data Risk</div>
            <div style={{ fontSize: "1.5rem", fontWeight: "700", color: fleetStats && fleetStats.unique_files_count > 0 ? "#FF5722" : "var(--accent-cyan)" }}>
              {fleetStats ? fleetStats.unique_files_count : 0} <span style={{ fontSize: "0.85rem", fontWeight: "400", color: "var(--text-muted)" }}>({fleetStats ? formatSize(fleetStats.unique_files_bytes) : "0 Bytes"})</span>
            </div>
          </div>
        </div>
      </div>

      <section className="glass-card comparison-picker" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "1.1rem" }}>
          <Cpu size={18} style={{ color: "var(--accent-cyan)" }} /> Pick Devices to Compare
        </h3>
        
        <div className="source-picker" style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: "1.5rem" }}>
          <div>
            <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.35rem" }}>Left Device (A)</label>
            <select 
              className="search-input"
              style={{ width: "100%", height: "42px", borderRadius: "8px", paddingLeft: "0.75rem" }}
              value={sourceX}
              onChange={(e) => setSourceX(e.target.value)}
            >
              <option value="" disabled>Select Device A...</option>
              {sources.map(s => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.status} - {s.kind})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", justifyContent: "center", paddingTop: "1.2rem" }}>
            <ArrowRightLeft size={20} style={{ color: "var(--text-muted)" }} />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.35rem" }}>Right Device (B)</label>
            <select 
              className="search-input"
              style={{ width: "100%", height: "42px", borderRadius: "8px", paddingLeft: "0.75rem" }}
              value={sourceY}
              onChange={(e) => setSourceY(e.target.value)}
            >
              <option value="" disabled>Select Device B...</option>
              {sources.map(s => (
                <option key={s.id} value={s.id} disabled={s.id === sourceX && sources.length > 1}>
                  {s.name} ({s.status} - {s.kind})
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {/* Managed Device Fleet Section */}
      <section className="glass-card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "1.1rem" }}>
          <Cpu size={18} style={{ color: "var(--accent-cyan)" }} /> Managed Device Fleet
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "1rem" }}>
          {sources.map(s => (
            <div key={s.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1rem", backgroundColor: "rgba(255,255,255,0.015)", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.03)" }}>
              <div>
                <strong style={{ fontSize: "0.95rem" }}>{s.name}</strong>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                  Kind: {s.kind}
                </div>
                <div style={{ fontSize: "0.75rem", marginTop: "0.15rem" }}>
                  Status: <span className={`audit-status ${s.status === 'online' ? 'completed' : s.status === 'decommissioned' ? 'undone' : 'failed'}`}>{s.status}</span>
                </div>
              </div>
              <div>
                {s.status !== "decommissioned" && (
                  <button 
                    className="btn btn-sm btn-danger"
                    onClick={() => handleDecommission(s)}
                    disabled={actionLoading}
                  >
                    Retire
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* AI Search Assistant Panel */}
      <section className="glass-card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "1.1rem" }}>
          <Sparkles size={18} style={{ color: "var(--accent-cyan)" }} /> Ask AI Search Assistant
        </h3>
        
        <div style={{ display: "flex", gap: "1rem" }}>
          <input 
            type="text" 
            className="search-input" 
            style={{ flex: 1, height: "42px", paddingLeft: "1rem", borderRadius: "8px" }}
            placeholder="e.g. Find files larger than 1MB on Left PC..."
            value={aiQueryText}
            onChange={(e) => setAiQueryText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleAiQuery(); }}
          />
          <button 
            className="btn btn-primary"
            style={{ height: "42px", display: "flex", alignItems: "center", gap: "0.35rem" }}
            onClick={handleAiQuery}
            disabled={loadingFiles || !aiQueryText.trim()}
          >
            <Sparkles size={16} />
            Ask AI
          </button>
        </div>

        {activeAiFilters && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: "rgba(0,188,212,0.1)", padding: "0.5rem 1rem", borderRadius: "6px" }}>
            <span style={{ fontSize: "0.85rem", color: "var(--accent-cyan)" }}>
              Active AI Filters: <strong>{JSON.stringify(activeAiFilters)}</strong>
            </span>
            <button 
              className="btn btn-sm btn-secondary" 
              onClick={handleClearAiFilters}
              style={{ minHeight: "26px", padding: "0.25rem 0.5rem" }}
            >
              Clear AI Search
            </button>
          </div>
        )}
      </section>

      {/* Live Summary Strip */}
      <section className="summary-grid">
        <div 
          className={`glass-card summary-card union ${viewType === "union" ? "active" : ""}`}
          onClick={() => setViewType("union")}
        >
          <div className="summary-card-info">
            <h4>Union (All Files)</h4>
            <div className="count">{summary.union_count}</div>
          </div>
          <div className="summary-card-icon" style={{ color: "var(--accent-blue)" }}>
            <Database size={24} />
          </div>
        </div>

        <div 
          className={`glass-card summary-card intersection ${viewType === "intersection" ? "active" : ""}`}
          onClick={() => setViewType("intersection")}
        >
          <div className="summary-card-info">
            <h4>Intersection</h4>
            <div className="count">{summary.intersection_count}</div>
          </div>
          <div className="summary-card-icon" style={{ color: "var(--success)" }}>
            <CheckCircle size={24} />
          </div>
        </div>

        <div 
          className={`glass-card summary-card only_a ${viewType === "only_a" ? "active" : ""}`}
          onClick={() => setViewType("only_a")}
        >
          <div className="summary-card-info">
            <h4>Only {nameX}</h4>
            <div className="count">{summary.only_a_count}</div>
          </div>
          <div className="summary-card-icon" style={{ color: "var(--purple)" }}>
            <HardDrive size={24} />
          </div>
        </div>

        <div 
          className={`glass-card summary-card only_b ${viewType === "only_b" ? "active" : ""}`}
          onClick={() => setViewType("only_b")}
        >
          <div className="summary-card-info">
            <h4>Only {nameY}</h4>
            <div className="count">{summary.only_b_count}</div>
          </div>
          <div className="summary-card-icon" style={{ color: "var(--accent-cyan)" }}>
            <HardDrive size={24} />
          </div>
        </div>

        <div 
          className={`glass-card summary-card conflicts ${viewType === "conflicts" ? "active" : ""}`}
          onClick={() => setViewType("conflicts")}
        >
          <div className="summary-card-info">
            <h4>Conflicts</h4>
            <div className="count">{summary.conflict_count}</div>
          </div>
          <div className="summary-card-icon" style={{ color: "var(--danger)" }}>
            <AlertTriangle size={24} />
          </div>
        </div>
      </section>

      {/* Inventory Status Panel */}
      {inventoryStatus && inventoryStatus.sources && inventoryStatus.sources.length > 0 && (
        <section className="glass-card" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
          {inventoryStatus.sources.map(s => (
            <div key={s.source_id}>
              <h3 style={{ marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <HardDrive size={18} style={{ color: s.source_id === sourceX ? "var(--purple)" : "var(--accent-cyan)" }} /> 
                {s.name} {s.source_id === sourceX ? "(A)" : s.source_id === sourceY ? "(B)" : ""}
              </h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Total Scanned: <strong>{s.count} files</strong></p>
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Last Scan: {formatDate(s.last_scan)}</p>
            </div>
          ))}
        </section>
      )}

      {/* Search & Filters */}
      <section className="toolbar">
        <div className="search-input-wrapper">
          <Search size={18} className="search-icon" />
          <input 
            type="text" 
            className="search-input" 
            placeholder="Fuzzy search file name, extension or path..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="filter-tabs">
          <button 
            className={`filter-tab ${viewType === "union" ? "active" : ""}`}
            onClick={() => setViewType("union")}
          >
            All Files
          </button>
          <button 
            className={`filter-tab ${viewType === "intersection" ? "active" : ""}`}
            onClick={() => setViewType("intersection")}
          >
            On Both
          </button>
          <button 
            className={`filter-tab ${viewType === "only_a" ? "active" : ""}`}
            onClick={() => setViewType("only_a")}
          >
            Only {nameX}
          </button>
          <button 
            className={`filter-tab ${viewType === "only_b" ? "active" : ""}`}
            onClick={() => setViewType("only_b")}
          >
            Only {nameY}
          </button>
          <button 
            className={`filter-tab ${viewType === "conflicts" ? "active" : ""}`}
            onClick={() => setViewType("conflicts")}
          >
            Conflicts
          </button>
        </div>
      </section>

      {/* Files Table */}
      <section className="glass-card" style={{ padding: 0 }}>
        <div className="table-container" onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}>
          {loadingFiles ? (
            <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>
              <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 1rem" }} />
              Loading files snapshot...
            </div>
          ) : !sourceX || !sourceY ? (
            <div className="empty-state">
              <HardDrive size={28} aria-hidden="true" />
              <strong>Choose two devices to begin</strong>
              <span>Select a left and right device above to inspect their file sets.</span>
            </div>
          ) : files.length === 0 ? (
            <div className="empty-state">
              <Search size={28} aria-hidden="true" />
              <strong>Nothing matches this view</strong>
              <span>Try a different set filter or clear the file search.</span>
            </div>
          ) : (
            <table className="file-table">
              <thead>
                <tr>
                  <th>File Name & Path</th>
                  <th>Size</th>
                  <th>Location</th>
                  <th>SHA-256 Hash</th>
                  <th style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {(() => {
                  const rowHeight = 72;
                  const viewportHeight = 600;
                  const totalRows = files.length;
                  const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - 3);
                  const endIndex = Math.min(totalRows, Math.ceil((scrollTop + viewportHeight) / rowHeight) + 3);
                  const paddingTop = startIndex * rowHeight;
                  const paddingBottom = Math.max(0, (totalRows - endIndex) * rowHeight);
                  const visibleFiles = files.slice(startIndex, endIndex);

                  return (
                    <>
                      {paddingTop > 0 && (
                        <tr style={{ height: `${paddingTop}px` }}><td colSpan={5} style={{ padding: 0 }} /></tr>
                      )}
                      {visibleFiles.map((file) => (
                        <tr key={file.id} style={{ height: `${rowHeight}px` }}>
                          <td>
                            <div className="file-name-cell">
                              <FileCode size={20} style={{ color: "var(--text-secondary)" }} />
                              <div>
                                <div>{file.name}</div>
                                <div className="file-path">{file.relative_path}</div>
                              </div>
                            </div>
                          </td>
                          <td>{formatSize(file.size_bytes)}</td>
                          <td>
                            <span className={`location-indicator ${file.location.toLowerCase()}`}>
                              {file.location === "Both" ? "Both Devices" : file.location === "Conflict" ? "Conflict" : file.location === "A" ? nameX : nameY}
                            </span>
                          </td>
                          <td>
                            <span className="file-hash" title={file.hash_sha256}>
                              {file.hash_sha256.substring(0, 8)}...
                            </span>
                          </td>
                          <td style={{ textAlign: "right" }}>
                            {file.location === "A" && (
                              <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                                <button 
                                  className="btn btn-sm btn-primary"
                                  onClick={() => handleOpenDryRun(file, "copy")}
                                >
                                  Copy to B
                                </button>
                                <button 
                                  className="btn btn-sm btn-secondary"
                                  onClick={() => addToDraftPlan(file, "copy")}
                                  style={{ border: "1px dashed var(--accent-cyan)", color: "var(--accent-cyan)" }}
                                >
                                  + Plan
                                </button>
                                <button 
                                  className="btn btn-sm text-danger"
                                  onClick={() => handleSafeDelete(file.relative_path, sourceX)}
                                >
                                  Delete
                                </button>
                              </div>
                            )}
                            {file.location === "B" && (
                              <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                                <button 
                                  className="btn btn-sm btn-primary"
                                  onClick={() => handleOpenDryRun(file, "copy")}
                                >
                                  Copy to A
                                </button>
                                <button 
                                  className="btn btn-sm btn-secondary"
                                  onClick={() => addToDraftPlan(file, "copy")}
                                  style={{ border: "1px dashed var(--accent-cyan)", color: "var(--accent-cyan)" }}
                                >
                                  + Plan
                                </button>
                                <button 
                                  className="btn btn-sm text-danger"
                                  onClick={() => handleSafeDelete(file.relative_path, sourceY)}
                                >
                                  Delete
                                </button>
                              </div>
                            )}
                            {file.location === "Both" && (
                              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginRight: "0.5rem" }}>
                                Synchronized
                              </span>
                            )}
                            {file.location === "Conflict" && (
                              <button 
                                className="btn btn-sm btn-danger"
                                onClick={() => setConflictModal({ open: true, row: file })}
                              >
                                Resolve
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                      {paddingBottom > 0 && (
                        <tr style={{ height: `${paddingBottom}px` }}><td colSpan={5} style={{ padding: 0 }} /></tr>
                      )}
                    </>
                  );
                })()}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </>
  );
}
