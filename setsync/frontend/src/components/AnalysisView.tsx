import { Trash2, RefreshCw, FileCode, Undo } from "lucide-react";

interface AnalysisViewProps {
  activeTab: "audit" | "dedupe" | "stale";
  duplicatesReport: any;
  dedupeMode: "exact" | "semantic";
  setDedupeMode: (mode: "exact" | "semantic") => void;
  loadingDedupe: boolean;
  handleSafeDelete: (relPath: string, srcId: string) => void;
  semanticThreshold: number;
  setSemanticThreshold: (val: number) => void;
  loadingSemantic: boolean;
  semanticDuplicates: any[];
  fetchSemanticDedupe: () => void;
  staleAgeDays: number;
  setStaleAgeDays: (days: number) => void;
  loadingStale: boolean;
  staleOrphans: any[];
  auditLogs: any[];
  sources: any[];
  handleUndo: (logId: string) => void;
  actionLoading: boolean;
  formatSize: (bytes: number) => string;
  formatDate: (iso?: string) => string;
}

export default function AnalysisView({
  activeTab,
  duplicatesReport,
  dedupeMode,
  setDedupeMode,
  loadingDedupe,
  handleSafeDelete,
  semanticThreshold,
  setSemanticThreshold,
  loadingSemantic,
  semanticDuplicates,
  fetchSemanticDedupe,
  staleAgeDays,
  setStaleAgeDays,
  loadingStale,
  staleOrphans,
  auditLogs,
  sources,
  handleUndo,
  actionLoading,
  formatSize,
  formatDate
}: AnalysisViewProps) {
  return (
    <>
      {/* Tab 2: Duplicates */}
      {activeTab === "dedupe" && (
        <section className="glass-card" style={{ gap: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "1.25rem" }}>Duplicate File Analyzer</h3>
              <p style={{ margin: "0.25rem 0 0 0", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                Find redundant files stored multiple times across your network.
              </p>
            </div>
            
            {duplicatesReport && dedupeMode === "exact" && (
              <div style={{ textAlign: "right" }}>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Space Reclaimable</span>
                <div style={{ fontSize: "1.75rem", fontWeight: "700", color: "var(--success)" }}>
                  {formatSize(duplicatesReport.space_reclaimable_bytes)}
                </div>
              </div>
            )}
          </div>

          <div style={{ display: "flex", gap: "1rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.75rem" }}>
            <button 
              className={`btn btn-sm ${dedupeMode === "exact" ? "btn-primary" : "btn-secondary"}`}
              onClick={() => setDedupeMode("exact")}
            >
              Exact Duplicates (SHA-256)
            </button>
            <button 
              className={`btn btn-sm ${dedupeMode === "semantic" ? "btn-primary" : "btn-secondary"}`}
              onClick={() => { setDedupeMode("semantic"); fetchSemanticDedupe(); }}
            >
              Visual Near-Duplicates (dHash)
            </button>
          </div>

          {dedupeMode === "exact" ? (
            loadingDedupe ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>
                <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 1rem" }} />
                Analyzing duplicate structures...
              </div>
            ) : !duplicatesReport || duplicatesReport.groups.length === 0 ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                No duplicate groups detected in your inventory! Excellent storage health.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                {duplicatesReport.groups.map((group: any) => (
                  <div 
                    key={group.hash_sha256} 
                    className="glass-card" 
                    style={{ padding: "1.25rem", backgroundColor: "rgba(255, 255, 255, 0.015)" }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.75rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.5rem" }}>
                      <div>
                        <strong style={{ fontSize: "0.95rem" }}>Hash: {group.hash_sha256.substring(0, 16)}...</strong>
                        <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Duplicate Count: {group.files.length} copies</div>
                      </div>
                      <div style={{ fontWeight: 600, color: "var(--accent-cyan)" }}>
                        {formatSize(group.size_bytes)} each
                      </div>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                      {group.files.map((file: any) => (
                        <div 
                          key={file.id} 
                          style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.5rem", backgroundColor: "rgba(255,255,255,0.02)", borderRadius: "6px" }}
                        >
                          <div>
                            <div style={{ fontSize: "0.9rem" }}>{file.path}</div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                              Device: <strong>{file.source_name}</strong> · Modified: {formatDate(file.mtime)}
                            </div>
                          </div>

                          <button 
                            className="btn btn-sm btn-danger"
                            onClick={() => handleSafeDelete(file.relative_path, file.source_id)}
                            style={{ minHeight: "30px", padding: "0.25rem 0.75rem" }}
                          >
                            <Trash2 size={13} style={{ marginRight: "0.25rem" }} />
                            Delete Copy
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "1rem", backgroundColor: "rgba(255,255,255,0.02)", padding: "0.75rem 1rem", borderRadius: "8px" }}>
                <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", minWidth: "300px" }}>
                  Hamming Distance Threshold: <strong>{semanticThreshold}</strong> (Lower = more similar)
                </span>
                <input 
                  type="range" 
                  min="0" 
                  max="64" 
                  value={semanticThreshold} 
                  onChange={(e) => setSemanticThreshold(Number(e.target.value))} 
                  style={{ flex: 1 }}
                />
              </div>

              {loadingSemantic ? (
                <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>
                  <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 1rem" }} />
                  Analyzing visual near-duplicates...
                </div>
              ) : semanticDuplicates.length === 0 ? (
                <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                  No visually similar image duplicates detected.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  {semanticDuplicates.map((group, idx) => (
                    <div key={idx} className="glass-card" style={{ padding: "1.25rem", backgroundColor: "rgba(255,255,255,0.015)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.75rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.5rem" }}>
                        <div>
                          <strong>Representative Hash: {group.representative_hash.substring(0, 16)}...</strong>
                          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Duplicate Count: {group.files.length} images</div>
                        </div>
                      </div>

                      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                        {group.files.map((file: any) => (
                          <div 
                            key={file.id} 
                            style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.5rem", backgroundColor: "rgba(255,255,255,0.02)", borderRadius: "6px" }}
                          >
                            <div>
                              <div style={{ fontSize: "0.9rem" }}>{file.path}</div>
                              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                                Device: <strong>{file.source_name}</strong> · dHash: <code style={{ color: "var(--accent-cyan)" }}>{file.image_hash}</code> · Size: {formatSize(file.size_bytes)}
                              </div>
                            </div>

                            <button 
                              className="btn btn-sm btn-danger"
                              onClick={() => handleSafeDelete(file.relative_path, file.source_id)}
                              style={{ minHeight: "30px", padding: "0.25rem 0.75rem" }}
                            >
                              <Trash2 size={13} style={{ marginRight: "0.25rem" }} />
                              Delete Copy
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* Tab 3: Stale Orphans */}
      {activeTab === "stale" && (
        <section className="glass-card" style={{ gap: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "1.25rem" }}>Stale / Orphan File Report</h3>
              <p style={{ margin: "0.25rem 0 0 0", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                Unique files present on only one device that have not been modified for a long time.
              </p>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Stale Age Threshold:</span>
              <select 
                className="search-input" 
                style={{ width: "120px", height: "36px", paddingLeft: "0.5rem", borderRadius: "6px" }}
                value={staleAgeDays}
                onChange={(e) => setStaleAgeDays(Number(e.target.value))}
              >
                <option value={30}>30 Days</option>
                <option value={90}>90 Days</option>
                <option value={180}>180 Days</option>
                <option value={365}>1 Year</option>
              </select>
            </div>
          </div>

          {loadingStale ? (
            <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>
              <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 1rem" }} />
              Analyzing unique file records...
            </div>
          ) : staleOrphans.length === 0 ? (
            <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
              No stale orphan files found.
            </div>
          ) : (
            <div className="table-container">
              <table className="file-table">
                <thead>
                  <tr>
                    <th>File Name & Path</th>
                    <th>Size</th>
                    <th>Source Device</th>
                    <th>Last Modified</th>
                    <th style={{ textAlign: "right" }}>Age</th>
                  </tr>
                </thead>
                <tbody>
                  {staleOrphans.map(file => (
                    <tr key={file.id}>
                      <td>
                        <div className="file-name-cell">
                          <FileCode size={20} style={{ color: "var(--text-secondary)" }} />
                          <div>
                            <div>{file.relative_path}</div>
                            <div className="file-path">{file.path}</div>
                          </div>
                        </div>
                      </td>
                      <td>{formatSize(file.size_bytes)}</td>
                      <td><strong>{file.source_name}</strong></td>
                      <td>{formatDate(file.mtime)}</td>
                      <td style={{ textAlign: "right", color: "var(--danger)", fontWeight: 600 }}>
                        {file.age_days} Days Old
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* Tab 4: Audit Logs View */}
      {activeTab === "audit" && (
        <section className="glass-card" style={{ padding: 0 }}>
          <div className="table-container">
            <table className="file-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>File</th>
                  <th>From Device</th>
                  <th>To Device</th>
                  <th>Status</th>
                  <th style={{ textAlign: "right" }}>Revert</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                      No audit records yet.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => {
                    const logSrcName = sources.find(s => s.id === log.source)?.name || `ID: ${log.source.substring(0,6)}`;
                    const logDstName = sources.find(s => s.id === log.destination)?.name || `ID: ${log.destination.substring(0,6)}`;
                    return (
                      <tr key={log.id}>
                        <td>{formatDate(log.timestamp)}</td>
                        <td style={{ fontWeight: 600 }}>{log.action_type.toUpperCase()}</td>
                        <td className="file-path">{log.file_path}</td>
                        <td>{logSrcName}</td>
                        <td>{logDstName}</td>
                        <td>
                          <span className={`audit-status ${log.status.toLowerCase()}`}>
                            {log.status}
                          </span>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {log.status === "completed" && (log.action_type === "copy" || log.action_type === "move") ? (
                            <button 
                              className="btn btn-sm btn-danger"
                              onClick={() => handleUndo(log.id)}
                              disabled={actionLoading}
                            >
                              <Undo size={14} style={{ marginRight: "0.25rem" }} />
                              Undo
                            </button>
                          ) : log.status === "undone" ? (
                            <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Reverted</span>
                          ) : (
                            "-"
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
