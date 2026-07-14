import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Database,
  Shield,
  WifiOff,
  RefreshCw,
  Lock,
  Play,
  Volume2,
  VolumeX,
  X,
  CheckCircle,
  Zap,
  Cpu,
  Network,
  Terminal
} from "lucide-react";

interface AdPlayerProps {
  onClose: () => void;
}

export default function AdPlayer({ onClose }: AdPlayerProps) {
  const [currentShot, setCurrentShot] = useState<1 | 2 | 3 | 4 | 5>(1);
  const [isPlaying, setIsPlaying] = useState(true);
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [shattering, setShattering] = useState(false);
  const [shot2ActiveIndex, setShot2ActiveIndex] = useState(0);
  const [glitchActive, setGlitchActive] = useState(false);
  const [particles, setParticles] = useState<Array<{ id: number; x: number; y: number; vx: number; vy: number; life: number; size: number }>>([]);
  const [typedText, setTypedText] = useState("");
  const [dataPackets, setDataPackets] = useState<Array<{ id: number; progress: number; failed: boolean }>>([]);

  const [progress, setProgress] = useState(0);
  const [transferStatus, setTransferStatus] = useState<"loading" | "failed" | "resuming" | "completed">("loading");

  const audioCtxRef = useRef<AudioContext | null>(null);
  const particleIntervalRef = useRef<any>(null);
  const packetIntervalRef = useRef<any>(null);

  // ==================== PARTICLE SYSTEM ====================
  const spawnParticles = useCallback((count: number, originX = 50, originY = 50) => {
    const newParticles = Array.from({ length: count }, (_, i) => ({
      id: Date.now() + i,
      x: originX,
      y: originY,
      vx: (Math.random() - 0.5) * 8,
      vy: (Math.random() - 0.5) * 8,
      life: 1,
      size: Math.random() * 4 + 2
    }));
    setParticles(prev => [...prev, ...newParticles]);
  }, []);

  // Update particles
  useEffect(() => {
    if (particles.length === 0) return;
    particleIntervalRef.current = setInterval(() => {
      setParticles(prev => prev
        .map(p => ({ ...p, x: p.x + p.vx, y: p.y + p.vy, life: p.life - 0.02, vy: p.vy + 0.1 }))
        .filter(p => p.life > 0)
      );
    }, 30);
    return () => clearInterval(particleIntervalRef.current);
  }, [particles.length > 0]);

  // ==================== AUDIO ENGINE ====================
  const playSound = (type: "reveal" | "shatter" | "ping" | "error" | "success" | "outro" | "glitch" | "digital" | "whoosh") => {
    if (!audioEnabled) return;
    try {
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      const ctx = audioCtxRef.current;
      const now = ctx.currentTime;

      const createOsc = (freq: number, type: OscillatorType, gainVal: number, start: number, dur: number, freqEnd?: number) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type;
        osc.frequency.setValueAtTime(freq, now + start);
        if (freqEnd) osc.frequency.exponentialRampToValueAtTime(freqEnd, now + start + dur);
        gain.gain.setValueAtTime(0.0001, now + start);
        gain.gain.linearRampToValueAtTime(gainVal, now + start + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + start + dur);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + start);
        osc.stop(now + start + dur + 0.05);
      };

      if (type === "reveal") {
        createOsc(80, "sine", 0.12, 0, 1.5, 600);
        createOsc(160, "sine", 0.06, 0.3, 1.2, 1200);
        createOsc(40, "sine", 0.15, 0, 1.5, 200);
      } else if (type === "shatter") {
        const bufferSize = ctx.sampleRate * 0.6;
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
          data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / bufferSize, 2);
        }
        const noise = ctx.createBufferSource();
        noise.buffer = buffer;
        const filter = ctx.createBiquadFilter();
        filter.type = "bandpass";
        filter.frequency.setValueAtTime(2000, now);
        filter.frequency.exponentialRampToValueAtTime(200, now + 0.6);
        filter.Q.setValueAtTime(3, now);
        const noiseGain = ctx.createGain();
        noiseGain.gain.setValueAtTime(0.25, now);
        noiseGain.gain.exponentialRampToValueAtTime(0.001, now + 0.6);
        noise.connect(filter);
        filter.connect(noiseGain);
        noiseGain.connect(ctx.destination);
        noise.start(now);
        noise.stop(now + 0.6);
        createOsc(300, "square", 0.08, 0, 0.15, 80);
        createOsc(500, "sawtooth", 0.06, 0.02, 0.1, 120);
      } else if (type === "ping") {
        createOsc(880, "triangle", 0.1, 0, 0.2);
        createOsc(1760, "sine", 0.04, 0.01, 0.15);
      } else if (type === "error") {
        createOsc(200, "sawtooth", 0.15, 0, 0.3, 80);
        createOsc(150, "square", 0.1, 0.05, 0.25, 50);
        createOsc(100, "sawtooth", 0.08, 0.1, 0.2, 40);
      } else if (type === "success") {
        createOsc(523.25, "sine", 0.12, 0, 0.2);
        createOsc(659.25, "sine", 0.12, 0.12, 0.2);
        createOsc(783.99, "sine", 0.12, 0.24, 0.3);
        createOsc(1046.5, "sine", 0.08, 0.36, 0.4);
        createOsc(1318.5, "triangle", 0.04, 0.4, 0.5);
      } else if (type === "outro") {
        createOsc(220, "sine", 0.12, 0, 2.5, 110);
        createOsc(330, "triangle", 0.06, 0, 2.5, 165);
        createOsc(440, "sine", 0.04, 0.5, 2.0);
        createOsc(110, "sine", 0.08, 0, 2.5, 55);
        createOsc(550, "sine", 0.03, 1.0, 1.5, 275);
      } else if (type === "glitch") {
        createOsc(1200, "square", 0.06, 0, 0.05);
        createOsc(800, "sawtooth", 0.04, 0.03, 0.04);
        createOsc(2400, "square", 0.03, 0.06, 0.03);
      } else if (type === "digital") {
        createOsc(1600, "square", 0.04, 0, 0.03);
        createOsc(2000, "square", 0.03, 0.04, 0.03);
        createOsc(2400, "square", 0.02, 0.08, 0.03);
        createOsc(1800, "square", 0.03, 0.12, 0.03);
      } else if (type === "whoosh") {
        const bufferSize = ctx.sampleRate * 0.4;
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
          data[i] = (Math.random() * 2 - 1) * Math.sin((i / bufferSize) * Math.PI);
        }
        const noise = ctx.createBufferSource();
        noise.buffer = buffer;
        const filter = ctx.createBiquadFilter();
        filter.type = "highpass";
        filter.frequency.setValueAtTime(200, now);
        filter.frequency.exponentialRampToValueAtTime(3000, now + 0.4);
        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
        noise.connect(filter);
        filter.connect(gain);
        gain.connect(ctx.destination);
        noise.start(now);
        noise.stop(now + 0.4);
      }
    } catch (e) {
      console.warn("Web Audio API not supported:", e);
    }
  };

  // ==================== TIMELINE ENGINE ====================
  useEffect(() => {
    if (!isPlaying) return;

    if (currentShot === 1) {
      playSound("reveal");
      setGlitchActive(false);

      const t0 = setTimeout(() => { playSound("whoosh"); }, 500);
      const t1 = setTimeout(() => {
        setShattering(true);
        setGlitchActive(true);
        playSound("shatter");
        playSound("glitch");
        spawnParticles(30, 50, 50);
        setTimeout(() => playSound("glitch"), 200);
        setTimeout(() => playSound("glitch"), 400);
      }, 3500);

      const t2 = setTimeout(() => {
        setShattering(false);
        setGlitchActive(false);
        playSound("digital");
        setCurrentShot(2);
      }, 4200);

      return () => { clearTimeout(t0); clearTimeout(t1); clearTimeout(t2); };
    }

    if (currentShot === 2) {
      setShot2ActiveIndex(0);
      playSound("ping");
      const interval = setInterval(() => {
        setShot2ActiveIndex(prev => {
          if (prev === 2) {
            clearInterval(interval);
            setTimeout(() => { playSound("whoosh"); setCurrentShot(3); }, 2500);
            return prev;
          }
          playSound("ping");
          spawnParticles(8, 50, 50);
          return prev + 1;
        });
      }, 2500);
      return () => clearInterval(interval);
    }

    if (currentShot === 3) {
      setProgress(0);
      setTransferStatus("loading");
      setDataPackets([
        { id: 0, progress: 0, failed: false },
        { id: 1, progress: 0, failed: false },
        { id: 2, progress: 0, failed: false }
      ]);

      let timer: any;
      let packetId = 0;

      // Animate data packets
      packetIntervalRef.current = setInterval(() => {
        setDataPackets(prev => prev.map((p, i) => {
          if (transferStatus === "failed" && Math.random() > 0.5) return p;
          return { ...p, progress: Math.min(p.progress + Math.random() * 15, 100) };
        }));
      }, 100);

      const step = () => {
        setProgress(prev => {
          if (prev < 54) {
            timer = setTimeout(step, 40);
            return prev + 2;
          } else if (prev === 54 && transferStatus === "loading") {
            setTransferStatus("failed");
            playSound("error");
            setGlitchActive(true);
            setTimeout(() => setGlitchActive(false), 1000);
            setDataPackets(prev => prev.map((p, i) => i === 1 ? { ...p, failed: true, progress: 0 } : p));
            timer = setTimeout(() => {
              setTransferStatus("resuming");
              playSound("ping");
              setDataPackets(prev => prev.map(p => ({ ...p, failed: false })));
              timer = setTimeout(() => {
                setTransferStatus("loading");
                step();
              }, 1200);
            }, 2000);
            return prev;
          } else if (prev >= 54 && prev < 100) {
            timer = setTimeout(step, 30);
            return prev + 2;
          } else if (prev >= 100) {
            setTransferStatus("completed");
            playSound("success");
            spawnParticles(40, 50, 50);
            timer = setTimeout(() => {
              playSound("whoosh");
              setCurrentShot(4);
            }, 2000);
            return 100;
          }
          return prev;
        });
      };

      timer = setTimeout(step, 200);
      return () => { clearTimeout(timer); clearInterval(packetIntervalRef.current); };
    }

    if (currentShot === 4) {
      playSound("reveal");
      playSound("digital");

      const t0 = setTimeout(() => playSound("digital"), 500);
      const t1 = setTimeout(() => playSound("digital"), 1000);
      const t2 = setTimeout(() => playSound("digital"), 1500);
      const t3 = setTimeout(() => playSound("ping"), 2000);
      const t4 = setTimeout(() => {
        playSound("whoosh");
        setCurrentShot(5);
      }, 4500);
      return () => { clearTimeout(t0); clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4); };
    }

    if (currentShot === 5) {
      playSound("outro");
      const fullText = "Secure. Resilient. Zero-Knowledge.";
      let charIdx = 0;
      const typeInterval = setInterval(() => {
        if (charIdx <= fullText.length) {
          setTypedText(fullText.slice(0, charIdx));
          if (charIdx % 3 === 0) playSound("digital");
          charIdx++;
        } else {
          clearInterval(typeInterval);
        }
      }, 50);

      const t = setTimeout(() => {
        spawnParticles(50, 50, 50);
        playSound("success");
        setCurrentShot(1);
      }, 7000);
      return () => { clearTimeout(t); clearInterval(typeInterval); };
    }
  }, [currentShot, isPlaying, audioEnabled]);

  // ==================== RENDER ====================
  return (
    <div className="promo-ad-player" style={styles.fullscreenOverlay}>
      <style dangerouslySetInnerHTML={{ __html: dynamicCSS }} />

      {/* Animated gradient background */}
      <div style={styles.animatedBg} />
      <div style={styles.gridOverlay} />
      <div style={styles.vignette} />

      {/* Glitch overlay */}
      {glitchActive && <div className="glitch-overlay" style={styles.glitchOverlay} />}
      <div className="scanlines" style={styles.scanlines} />

      {/* Floating particles */}
      {particles.map(p => (
        <div key={p.id} style={{
          position: "absolute",
          left: `${p.x}%`,
          top: `${p.y}%`,
          width: `${p.size}px`,
          height: `${p.size}px`,
          borderRadius: "50%",
          background: p.life > 0.5 ? "var(--accent-cyan)" : "var(--accent-purple)",
          opacity: p.life,
          boxShadow: `0 0 ${p.size * 3}px var(--accent-cyan)`,
          pointerEvents: "none",
          zIndex: 100,
          transition: "none"
        }} />
      ))}

      {/* Top Header bar */}
      <div style={styles.topBar}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div style={styles.logoOrb}>
            <Database size={16} style={{ color: "#030712" }} />
          </div>
          <span style={{ fontWeight: 600, letterSpacing: "2px", fontSize: "0.8rem", color: "#e2e8f0" }}>
            SETSYNC ENTERPRISE
          </span>
          <div style={styles.liveBadge}>
            <div style={styles.liveDot} />
            <span style={{ fontSize: "0.65rem", fontWeight: 700, letterSpacing: "1px" }}>LIVE</span>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <button onClick={() => setAudioEnabled(!audioEnabled)} style={styles.controlBtn} title={audioEnabled ? "Mute Audio" : "Enable Audio"}>
            {audioEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
          </button>
          <button onClick={() => setIsPlaying(!isPlaying)} style={styles.controlBtn} title={isPlaying ? "Pause" : "Play"}>
            <Play size={16} style={{ transform: isPlaying ? "none" : "rotate(90deg)", color: isPlaying ? "#94a3b8" : "var(--accent-cyan)" }} />
          </button>
          <button onClick={onClose} style={styles.closeBtn}>
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Main Screen Content */}
      <div style={styles.mainCanvas}>

        {/* ==================== SHOT 1: OPENING REVEAL ==================== */}
        {currentShot === 1 && (
          <div style={styles.shotContainer}>
            {/* Expanding ring waves */}
            <div style={{ ...styles.ringWave, animation: "ringExpand 2s ease-out infinite" }} />
            <div style={{ ...styles.ringWave, animation: "ringExpand 2s ease-out infinite 0.7s" }} />
            <div style={{ ...styles.ringWave, animation: "ringExpand 2s ease-out infinite 1.4s" }} />

            <div style={{ ...styles.glowCore, animation: "pulseNeon 1.5s ease-in-out infinite" }} />

            <div style={{
              ...styles.logoSpace,
              animation: shattering ? "shatterExplode 0.6s ease-out forwards" : "logoFlyForward 4s cubic-bezier(0.16, 1, 0.3, 1) forwards"
            }}>
              <div style={styles.logoHexFrame}>
                <Database size={100} style={styles.logoIcon} />
              </div>
              <h1 style={styles.logoText}>
                Set<span style={{ color: "var(--accent-cyan)" }}>Sync</span>
              </h1>
              <div style={styles.glowReflect} />
              <div style={styles.tagline}>MULTI-DEVICE SYNC</div>
            </div>

            {/* Orbiting particles */}
            <div className="orbiting-ring" style={{ ...styles.orbitRingA, animation: "spin 20s linear infinite" }}>
              <div style={styles.orbitDot} />
            </div>
            <div className="orbiting-ring" style={{ ...styles.orbitRingB, animation: "spin 35s linear infinite reverse" }}>
              <div style={{ ...styles.orbitDot, background: "var(--accent-purple)", boxShadow: "0 0 8px var(--accent-purple)" }} />
            </div>
            <div className="orbiting-ring" style={{ ...styles.orbitRingC, animation: "spin 50s linear infinite" }}>
              <div style={{ ...styles.orbitDot, width: "6px", height: "6px" }} />
            </div>

            {/* Shatter Overlay */}
            {shattering && (
              <div style={styles.shatterOverlay}>
                {[0, 45, 90, 135, 180, 225, 270, 315].map((angle, i) => {
                  const rad = (angle * Math.PI) / 180;
                  const dist = 300 + Math.random() * 200;
                  return (
                    <div key={i} style={{
                      ...styles.shatterShard,
                      animation: `shardFly${i} 0.6s ease-out forwards`,
                      transform: `rotate(${angle}deg)`
                    }} />
                  );
                })}
                {/* Shockwave */}
                <div style={{ ...styles.shockwave, animation: "shockwave 0.5s ease-out forwards" }} />
              </div>
            )}
          </div>
        )}

        {/* ==================== SHOT 2: FEATURE SHOWCASE ==================== */}
        {currentShot === 2 && (
          <div style={styles.shotContainer}>
            <h3 style={styles.shotTitle}>
              <span style={{ color: "var(--accent-cyan)" }}>//</span> Zero-Trust Architecture
            </h3>

            {/* Connection lines SVG */}
            <svg style={styles.connectionLines} viewBox="0 0 600 200">
              <defs>
                <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="var(--accent-cyan)" stopOpacity="0" />
                  <stop offset="50%" stopColor="var(--accent-cyan)" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="var(--accent-cyan)" stopOpacity="0" />
                </linearGradient>
              </defs>
              <line x1="100" y1="100" x2="300" y2="100" stroke="url(#lineGrad)" strokeWidth="2" strokeDasharray="5,5" className="dash-line" />
              <line x1="300" y1="100" x2="500" y2="100" stroke="url(#lineGrad)" strokeWidth="2" strokeDasharray="5,5" className="dash-line" />
            </svg>

            <div style={styles.featureRing}>
              {[
                { icon: Lock, label: "Zero-Knowledge", desc: "Local Encryption Keys", body: "Tenant metadata is encrypted client-side using deterministic AES-256 before being uploaded. The coordinator hosts hold key RAM contexts ephemeral, ensuring true Zero-Knowledge secrecy." },
                { icon: RefreshCw, label: "Resilient Sync", desc: "Block-Level Chunk Transfer", body: "Splits large payloads (like 10GB DBs) into verified block chunks. Recovers dynamically from intermediate packets during drops, avoiding complete file corruption." },
                { icon: Shield, label: "Tenant RLS", desc: "SQL Row-Level Security", body: "Enforces strict tenant isolation directly in the PostgreSQL storage layer. Restricts queries using connection parameter namespaces to safeguard against API leaks." }
              ].map((feat, i) => {
                const Icon = feat.icon;
                const isActive = shot2ActiveIndex === i;
                return (
                  <div key={i} style={{
                    ...styles.featureIconBlock,
                    borderColor: isActive ? "var(--accent-cyan)" : "rgba(255,255,255,0.1)",
                    transform: isActive ? "scale(1.15) rotateY(0deg)" : "scale(0.9) rotateY(10deg)",
                    boxShadow: isActive ? "0 0 40px rgba(0,242,254,0.4), inset 0 0 20px rgba(0,242,254,0.1)" : "none",
                    background: isActive ? "rgba(0,242,254,0.05)" : "rgba(255,255,255,0.02)"
                  }}>
                    {isActive && <div style={{ ...styles.featurePulse, animation: "featurePulse 1.5s ease-in-out infinite" }} />}
                    <Icon size={36} style={{
                      color: isActive ? "var(--accent-cyan)" : "#475569",
                      animation: isActive && i === 1 ? "spin 2s linear infinite" : "none",
                      filter: isActive ? "drop-shadow(0 0 10px var(--accent-cyan))" : "none",
                      transition: "color 0.3s, filter 0.3s",
                      zIndex: 2
                    }} />
                    <span style={{ ...styles.featureLabel, color: isActive ? "#fff" : "#64748b" }}>{feat.label}</span>
                    {isActive && <div style={styles.activeIndicator} />}
                  </div>
                );
              })}
            </div>

            {/* Feature Description Card */}
            <div style={{
              ...styles.detailCard,
              borderColor: "rgba(0,242,254,0.2)",
              boxShadow: "0 10px 40px rgba(0,0,0,0.5), 0 0 20px rgba(0,242,254,0.05)"
            }}>
              <div style={styles.detailCardContent} key={shot2ActiveIndex}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                  <div style={{ width: "3px", height: "20px", background: "var(--accent-cyan)", borderRadius: "2px", boxShadow: "0 0 8px var(--accent-cyan)" }} />
                  <h4 style={{ color: "var(--accent-cyan)", margin: 0, fontSize: "1.1rem" }}>
                    {shot2ActiveIndex === 0 && "Local Encryption Keys"}
                    {shot2ActiveIndex === 1 && "Block-Level Chunk Transfer"}
                    {shot2ActiveIndex === 2 && "SQL Row-Level Security"}
                  </h4>
                </div>
                <p style={{ margin: 0, color: "#94a3b8", fontSize: "0.9rem", lineHeight: "1.7", paddingLeft: "0.75rem" }}>
                  {shot2ActiveIndex === 0 && "Tenant metadata is encrypted client-side using deterministic AES-256 before being uploaded. The coordinator hosts hold key RAM contexts ephemeral, ensuring true Zero-Knowledge secrecy."}
                  {shot2ActiveIndex === 1 && "Splits large payloads (like 10GB DBs) into verified block chunks. Recovers dynamically from intermediate packets during drops, avoiding complete file corruption."}
                  {shot2ActiveIndex === 2 && "Enforces strict tenant isolation directly in the PostgreSQL storage layer. Restricts queries using connection parameter namespaces to safeguard against API leaks."}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ==================== SHOT 3: NETWORK FAILURE & RECOVERY ==================== */}
        {currentShot === 3 && (
          <div style={styles.shotContainer}>
            <h3 style={styles.shotTitle}>
              <span style={{ color: "var(--accent-cyan)" }}>//</span> Resilient Transfer Protocol
            </h3>

            <div style={{
              ...styles.transferWidget,
              borderColor: transferStatus === "failed" ? "rgba(239,68,68,0.3)" : "rgba(0,242,254,0.15)",
              transition: "border-color 0.3s"
            }}>
              {/* Animated header */}
              <div style={styles.transferHeader}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <Terminal size={14} style={{ color: "var(--accent-cyan)" }} />
                  <span style={{ fontSize: "0.8rem", color: "#94a3b8", fontFamily: "monospace" }}>
                    syncing: database_nightly_backup.db
                  </span>
                </div>
                <span style={{
                  fontSize: "0.9rem",
                  fontWeight: 800,
                  fontFamily: "monospace",
                  color: transferStatus === "failed" ? "var(--danger)" : "var(--accent-cyan)",
                  textShadow: transferStatus === "failed" ? "0 0 10px var(--danger)" : "0 0 10px var(--accent-cyan)"
                }}>
                  {progress}%
                </span>
              </div>

              {/* Chunk packet visualization */}
              <div style={styles.packetRow}>
                {dataPackets.map((pkt, i) => (
                  <div key={i} style={{
                    ...styles.packetBlock,
                    borderColor: pkt.failed ? "var(--danger)" : pkt.progress >= 100 ? "var(--success)" : "var(--accent-cyan)",
                    background: pkt.failed ? "rgba(239,68,68,0.1)" : pkt.progress >= 100 ? "rgba(34,197,94,0.1)" : "rgba(0,242,254,0.05)"
                  }}>
                    <div style={{
                      position: "absolute",
                      bottom: 0,
                      left: 0,
                      right: 0,
                      height: `${pkt.progress}%`,
                      background: pkt.failed ? "var(--danger)" : pkt.progress >= 100 ? "var(--success)" : "var(--accent-cyan)",
                      opacity: 0.3,
                      transition: "height 0.1s",
                      borderRadius: "4px"
                    }} />
                    <span style={{ position: "relative", zIndex: 2, fontSize: "0.65rem", fontWeight: 700, fontFamily: "monospace", color: pkt.failed ? "var(--danger)" : "#e2e8f0" }}>
                      {pkt.failed ? "ERR" : pkt.progress >= 100 ? "OK" : `C${i + 1}`}
                    </span>
                  </div>
                ))}
              </div>

              {/* Progress Bar */}
              <div style={styles.progressBarBg}>
                <div style={{
                  ...styles.progressBarFill,
                  width: `${progress}%`,
                  background: transferStatus === "failed"
                    ? "linear-gradient(90deg, var(--danger), #dc2626)"
                    : "linear-gradient(90deg, var(--accent-cyan), #0891b2)",
                  boxShadow: transferStatus === "failed" ? "0 0 15px rgba(239,68,68,0.6)" : "0 0 20px rgba(0,242,254,0.5)"
                }} />
                {/* Animated shimmer */}
                <div style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  height: "100%",
                  width: "30px",
                  background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent)",
                  animation: "shimmer 1.5s linear infinite",
                  borderRadius: "5px"
                }} />
              </div>

              {/* Status Banner */}
              <div style={styles.statusBanner}>
                {transferStatus === "loading" && (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#e2e8f0" }}>
                    <RefreshCw className="spinning" size={16} style={{ animation: "spin 1s linear infinite" }} />
                    <span style={{ fontFamily: "monospace" }}>Uploading chunk {progress < 54 ? "1" : "3"}/3...</span>
                  </div>
                )}
                {transferStatus === "failed" && (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--danger)", animation: "blinkRed 0.4s ease infinite alternate" }}>
                    <WifiOff size={18} />
                    <span style={{ fontWeight: 700, fontFamily: "monospace", fontSize: "0.8rem" }}>CONNECTION LOST — RETRYING CHUNKS</span>
                  </div>
                )}
                {transferStatus === "resuming" && (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--accent-cyan)" }}>
                    <RefreshCw size={16} style={{ animation: "spin 0.8s linear infinite" }} />
                    <span style={{ fontFamily: "monospace" }}>Resuming from block 1 — Signature verified</span>
                  </div>
                )}
                {transferStatus === "completed" && (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--success)", animation: "successPulse 0.5s ease" }}>
                    <CheckCircle size={18} />
                    <span style={{ fontWeight: 700, fontFamily: "monospace", fontSize: "0.8rem" }}>TRANSFER COMPLETE — SHA-256 VERIFIED</span>
                  </div>
                )}
              </div>
            </div>

            {/* Tech stats footer */}
            <div style={styles.techStats}>
              <div style={styles.statItem}>
                <Cpu size={14} style={{ color: "var(--accent-cyan)" }} />
                <span style={styles.statValue}>AES-256</span>
              </div>
              <div style={styles.statItem}>
                <Network size={14} style={{ color: "var(--accent-cyan)" }} />
                <span style={styles.statValue}>SHA-256</span>
              </div>
              <div style={styles.statItem}>
                <Zap size={14} style={{ color: "var(--accent-cyan)" }} />
                <span style={styles.statValue}>10GB MAX</span>
              </div>
            </div>
          </div>
        )}

        {/* ==================== SHOT 4: SECURITY MATRIX ==================== */}
        {currentShot === 4 && (
          <div style={styles.shotContainer}>
            <div style={styles.matrixBackground}>
              {Array.from({ length: 20 }).map((_, idx) => (
                <div key={idx} style={{
                  ...styles.matrixCol,
                  left: `${idx * 5}%`,
                  animationDelay: `${idx * 0.1}s`,
                  animationDuration: `${3 + Math.random() * 2}s`
                }}>
                  {Array.from({ length: 15 }).map((_, charIdx) => (
                    <span key={charIdx} style={{
                      ...styles.matrixChar,
                      color: charIdx < 3 ? "#fff" : "var(--accent-cyan)",
                      opacity: 1 - charIdx * 0.06,
                      textShadow: charIdx < 3 ? "0 0 10px #fff" : "0 0 5px var(--accent-cyan)"
                    }}>
                      {Math.random() > 0.5 ? "1" : "0"}
                    </span>
                  ))}
                </div>
              ))}
            </div>

            {/* Glowing shield with hexagon frame */}
            <div style={{
              ...styles.shieldWrapper,
              animation: "shieldAssemble 1.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards"
            }}>
              {/* Rotating hexagon ring */}
              <div style={{
                ...styles.hexRing,
                animation: "spin 8s linear infinite"
              }} />
              <div style={{
                ...styles.hexRing2,
                animation: "spin 12s linear infinite reverse"
              }} />

              <Shield size={100} style={{
                color: "var(--accent-cyan)",
                filter: "drop-shadow(0 0 25px rgba(0,242,254,0.6))",
                position: "relative",
                zIndex: 3
              }} />
              <div style={styles.shieldLockCenter}>
                <Lock size={28} style={{ color: "#030712" }} />
              </div>
            </div>

            <h4 style={{ ...styles.matrixTitle, animation: "fadeUp 1s ease 0.8s both" }}>
              PostgreSQL Row-Level Security
            </h4>
            <p style={{ ...styles.matrixSubTitle, animation: "fadeUp 1s ease 1.2s both" }}>
              Shielded · Encrypted · Isolated
            </p>
          </div>
        )}

        {/* ==================== SHOT 5: BRAND OUTRO ==================== */}
        {currentShot === 5 && (
          <div style={styles.shotContainer}>
            <div style={{ ...styles.outroBlock, animation: "fadeInOutro 1.5s ease forwards" }}>
              {/* Pulsing orb behind logo */}
              <div style={{ ...styles.outroOrb, animation: "pulseNeon 2s ease-in-out infinite" }} />

              <div style={styles.logoHexFrame}>
                <Database size={64} style={{ color: "var(--accent-cyan)", filter: "drop-shadow(0 0 20px rgba(0,242,254,0.5))" }} />
              </div>
              <h1 style={{
                fontSize: "4rem",
                fontWeight: 800,
                letterSpacing: "3px",
                margin: "1.5rem 0 0.5rem 0",
                color: "#fff",
                animation: "textGlow 2s ease-in-out infinite alternate"
              }}>
                Set<span style={{ color: "var(--accent-cyan)" }}>Sync</span>
              </h1>
              <div style={styles.dividerAccent} />
              <p style={{ fontSize: "1.1rem", color: "#94a3b8", margin: "1rem 0", maxWidth: "600px", lineHeight: "1.8", textAlign: "center" }}>
                State-of-the-Art Multi-Device File Synchronization.
              </p>
              <div style={{
                fontSize: "1.3rem",
                color: "var(--accent-cyan)",
                fontWeight: 700,
                fontFamily: "monospace",
                textShadow: "0 0 15px var(--accent-cyan)",
                minHeight: "2rem"
              }}>
                {typedText}<span style={{ animation: "cursorBlink 0.7s step-end infinite" }}>|</span>
              </div>

              {/* CTA badges */}
              <div style={styles.outroBadges}>
                {["AES-256", "SHA-256", "Zero-Knowledge", "PostgreSQL RLS"].map(badge => (
                  <div key={badge} style={styles.outroBadge}>{badge}</div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Timeline indicator */}
      <div style={styles.timelineContainer}>
        <div style={styles.timelineLabels}>
          {["Intro", "Features", "Resilience", "Security", "Brand"].map((label, i) => (
            <span key={label} style={{
              fontSize: "0.65rem",
              fontWeight: 600,
              letterSpacing: "1px",
              color: currentShot === i + 1 ? "var(--accent-cyan)" : "#475569",
              transition: "color 0.3s"
            }}>
              {label}
            </span>
          ))}
        </div>
        <div style={styles.timelineBar}>
          {([1, 2, 3, 4, 5] as const).map(num => (
            <div key={num} onClick={() => setCurrentShot(num)} style={{
              ...styles.timelineDot,
              backgroundColor: currentShot === num ? "var(--accent-cyan)" : "#1e293b",
              boxShadow: currentShot === num ? "0 0 12px var(--accent-cyan)" : "none",
              width: currentShot === num ? "32px" : "10px",
              height: currentShot === num ? "6px" : "6px"
            }} title={`Shot ${num}`} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ==========================================
// DYNAMIC CSS
// ==========================================
const dynamicCSS = `
@keyframes pulseNeon {
  0%, 100% { box-shadow: 0 0 30px rgba(0, 242, 254, 0.2); }
  50% { box-shadow: 0 0 60px rgba(0, 242, 254, 0.5); }
}

@keyframes logoFlyForward {
  0% { transform: scale(0.1) rotate(-20deg); opacity: 0; filter: blur(20px); }
  15% { opacity: 1; filter: blur(0px); }
  85% { transform: scale(1.1) rotate(0deg); filter: blur(0px); }
  100% { transform: scale(1.5) rotate(0deg); opacity: 0; filter: blur(10px); }
}

@keyframes shatterExplode {
  0% { transform: scale(1.5) rotate(0deg); opacity: 1; }
  50% { transform: scale(1.8) rotate(5deg); opacity: 0.5; filter: brightness(2); }
  100% { transform: scale(3) rotate(15deg); opacity: 0; filter: blur(30px); }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes blinkRed {
  from { opacity: 0.3; }
  to { opacity: 1; }
}

@keyframes shieldAssemble {
  0% { transform: scale(0.1) rotate(-180deg); opacity: 0; filter: blur(20px); }
  60% { transform: scale(1.2) rotate(20deg); opacity: 1; filter: blur(0px); }
  100% { transform: scale(1) rotate(0deg); opacity: 1; }
}

@keyframes fadeUp {
  0% { transform: translateY(30px); opacity: 0; }
  100% { transform: translateY(0); opacity: 1; }
}

@keyframes fadeInOutro {
  0% { transform: scale(0.9) translateY(20px); opacity: 0; filter: blur(10px); }
  100% { transform: scale(1) translateY(0); opacity: 1; filter: blur(0px); }
}

@keyframes rain {
  0% { transform: translateY(-100%); opacity: 0; }
  10% { opacity: 0.8; }
  90% { opacity: 0.8; }
  100% { transform: translateY(200%); opacity: 0; }
}

@keyframes ringExpand {
  0% { width: 100px; height: 100px; opacity: 0.6; border-width: 2px; }
  100% { width: 800px; height: 800px; opacity: 0; border-width: 1px; }
}

@keyframes shockwave {
  0% { width: 50px; height: 50px; opacity: 1; border-width: 4px; }
  100% { width: 1000px; height: 1000px; opacity: 0; border-width: 1px; }
}

@keyframes shardFly0 { 0% { transform: rotate(0deg) translate(0,0); opacity: 1; } 100% { transform: rotate(0deg) translate(-300px,-300px); opacity: 0; } }
@keyframes shardFly1 { 0% { transform: rotate(45deg) translate(0,0); opacity: 1; } 100% { transform: rotate(45deg) translate(0,-350px); opacity: 0; } }
@keyframes shardFly2 { 0% { transform: rotate(90deg) translate(0,0); opacity: 1; } 100% { transform: rotate(90deg) translate(350px,-300px); opacity: 0; } }
@keyframes shardFly3 { 0% { transform: rotate(135deg) translate(0,0); opacity: 1; } 100% { transform: rotate(135deg) translate(400px,0); opacity: 0; } }
@keyframes shardFly4 { 0% { transform: rotate(180deg) translate(0,0); opacity: 1; } 100% { transform: rotate(180deg) translate(350px,350px); opacity: 0; } }
@keyframes shardFly5 { 0% { transform: rotate(225deg) translate(0,0); opacity: 1; } 100% { transform: rotate(225deg) translate(0,400px); opacity: 0; } }
@keyframes shardFly6 { 0% { transform: rotate(270deg) translate(0,0); opacity: 1; } 100% { transform: rotate(270deg) translate(-350px,350px); opacity: 0; } }
@keyframes shardFly7 { 0% { transform: rotate(315deg) translate(0,0); opacity: 1; } 100% { transform: rotate(315deg) translate(-400px,0); opacity: 0; } }

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(calc(500px)); }
}

@keyframes featurePulse {
  0%, 100% { transform: scale(1); opacity: 0.3; }
  50% { transform: scale(1.3); opacity: 0; }
}

@keyframes successPulse {
  0% { transform: scale(0.8); opacity: 0; }
  50% { transform: scale(1.1); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}

@keyframes textGlow {
  0% { text-shadow: 0 0 10px rgba(0,242,254,0.3); }
  100% { text-shadow: 0 0 30px rgba(0,242,254,0.8), 0 0 60px rgba(0,242,254,0.3); }
}

@keyframes cursorBlink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes gradientShift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

@keyframes dashMove {
  0% { stroke-dashoffset: 0; }
  100% { stroke-dashoffset: -20; }
}

.glitch-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(90deg, rgba(255,0,0,0.05), rgba(0,255,255,0.05), rgba(255,0,255,0.05));
  mix-blend-mode: screen;
  animation: glitchShift 0.1s steps(2) infinite;
  z-index: 50;
  pointer-events: none;
}

@keyframes glitchShift {
  0% { transform: translateX(-2px); }
  100% { transform: translateX(2px); }
}

.scanlines {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.06) 2px,
    rgba(0, 0, 0, 0.06) 4px
  );
  pointer-events: none;
  z-index: 49;
}

.dash-line {
  animation: dashMove 0.5s linear infinite;
}
`;

const styles: Record<string, React.CSSProperties> = {
  fullscreenOverlay: {
    position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "#030712",
    zIndex: 9999,
    display: "flex", flexDirection: "column",
    fontFamily: "Inter, system-ui, -apple-system, sans-serif",
    overflow: "hidden"
  },
  animatedBg: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    background: "radial-gradient(ellipse at 30% 20%, rgba(0,242,254,0.06) 0%, transparent 50%), radial-gradient(ellipse at 70% 80%, rgba(139,92,246,0.04) 0%, transparent 50%)",
    backgroundSize: "200% 200%",
    animation: "gradientShift 15s ease infinite",
    zIndex: 0
  },
  gridOverlay: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    backgroundImage: "linear-gradient(rgba(0,242,254,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,242,254,0.03) 1px, transparent 1px)",
    backgroundSize: "40px 40px",
    zIndex: 1,
    pointerEvents: "none"
  },
  vignette: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    background: "radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.6) 100%)",
    zIndex: 2,
    pointerEvents: "none"
  },
  glitchOverlay: {} as React.CSSProperties,
  scanlines: {} as React.CSSProperties,
  topBar: {
    padding: "0.75rem 2rem",
    borderBottom: "1px solid rgba(255,255,255,0.05)",
    display: "flex", justifyContent: "space-between", alignItems: "center",
    zIndex: 10,
    background: "rgba(3,7,18,0.8)",
    backdropFilter: "blur(10px)"
  },
  logoOrb: {
    width: "28px", height: "28px",
    borderRadius: "50%",
    background: "linear-gradient(135deg, var(--accent-cyan), #0891b2)",
    display: "flex", alignItems: "center", justifyContent: "center",
    boxShadow: "0 0 12px rgba(0,242,254,0.4)"
  },
  liveBadge: {
    display: "flex", alignItems: "center", gap: "0.3rem",
    padding: "0.15rem 0.5rem",
    borderRadius: "4px",
    background: "rgba(239,68,68,0.1)",
    border: "1px solid rgba(239,68,68,0.3)"
  },
  liveDot: {
    width: "6px", height: "6px", borderRadius: "50%",
    background: "#ef4444",
    animation: "blinkRed 0.8s ease infinite alternate"
  },
  controlBtn: {
    background: "transparent", border: "none", color: "#64748b",
    cursor: "pointer", padding: "0.5rem", borderRadius: "8px",
    display: "flex", alignItems: "center",
    transition: "color 0.2s, background-color 0.2s"
  },
  closeBtn: {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.08)",
    color: "#94a3b8", cursor: "pointer", padding: "0.5rem",
    borderRadius: "8px", display: "flex", alignItems: "center",
    transition: "all 0.2s"
  },
  mainCanvas: {
    flex: 1, display: "flex", justifyContent: "center", alignItems: "center",
    position: "relative", overflow: "hidden", zIndex: 5
  },
  shotContainer: {
    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
    width: "100%", height: "100%", position: "relative"
  },
  ringWave: {
    position: "absolute", width: "100px", height: "100px",
    borderRadius: "50%", border: "2px solid rgba(0,242,254,0.3)",
    pointerEvents: "none"
  },
  glowCore: {
    width: "200px", height: "200px", borderRadius: "50%",
    background: "radial-gradient(circle, rgba(0,242,254,0.3) 0%, transparent 70%)",
    position: "absolute", filter: "blur(30px)"
  },
  logoSpace: {
    display: "flex", flexDirection: "column", alignItems: "center",
    position: "relative", zIndex: 5
  },
  logoHexFrame: {
    width: "140px", height: "140px",
    display: "flex", alignItems: "center", justifyContent: "center",
    borderRadius: "20px",
    background: "rgba(0,242,254,0.03)",
    border: "1px solid rgba(0,242,254,0.2)",
    boxShadow: "inset 0 0 30px rgba(0,242,254,0.05)"
  },
  logoIcon: {
    color: "var(--accent-cyan)",
    filter: "drop-shadow(0 0 25px rgba(0,242,254,0.5))"
  },
  logoText: {
    fontSize: "3.5rem", fontWeight: 800, color: "#fff",
    letterSpacing: "4px", margin: "1rem 0 0 0",
    textShadow: "0 2px 20px rgba(0,0,0,0.8)"
  },
  tagline: {
    fontSize: "0.7rem", fontWeight: 600, letterSpacing: "6px",
    color: "rgba(0,242,254,0.5)", marginTop: "0.25rem"
  },
  glowReflect: {
    position: "absolute", bottom: "-15px",
    width: "250px", height: "2px",
    background: "linear-gradient(90deg, transparent, var(--accent-cyan), transparent)",
    boxShadow: "0 0 10px var(--accent-cyan)"
  },
  orbitRingA: {
    position: "absolute", width: "350px", height: "350px",
    border: "1px dashed rgba(0,242,254,0.12)", borderRadius: "50%"
  },
  orbitRingB: {
    position: "absolute", width: "480px", height: "480px",
    border: "1px dashed rgba(139,92,246,0.08)", borderRadius: "50%"
  },
  orbitRingC: {
    position: "absolute", width: "600px", height: "600px",
    border: "1px solid rgba(255,255,255,0.03)", borderRadius: "50%"
  },
  orbitDot: {
    position: "absolute", top: "-4px", left: "50%",
    width: "8px", height: "8px", borderRadius: "50%",
    background: "var(--accent-cyan)",
    boxShadow: "0 0 10px var(--accent-cyan)"
  },
  shatterOverlay: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 10, display: "flex", flexWrap: "wrap",
    justifyContent: "center", alignItems: "center",
    pointerEvents: "none"
  },
  shatterShard: {
    width: "150px", height: "150px",
    background: "rgba(255,255,255,0.08)",
    border: "1px solid rgba(255,255,255,0.3)",
    backdropFilter: "blur(5px)", position: "absolute",
    clipPath: "polygon(50% 0%, 0% 100%, 100% 100%)"
  },
  shockwave: {
    position: "absolute", top: "50%", left: "50%",
    transform: "translate(-50%,-50%)",
    borderRadius: "50%",
    border: "4px solid var(--accent-cyan)",
    pointerEvents: "none"
  },
  shotTitle: {
    fontSize: "1.4rem", fontWeight: 700, letterSpacing: "2px",
    color: "#fff", margin: "0 0 3rem 0", textTransform: "uppercase",
    fontFamily: "monospace"
  },
  connectionLines: {
    position: "absolute", top: "40%", left: "50%",
    transform: "translate(-50%,-50%)", width: "600px", height: "200px",
    zIndex: 0, opacity: 0.6
  },
  featureRing: {
    display: "flex", gap: "3rem", justifyContent: "center", alignItems: "center",
    marginBottom: "2.5rem", position: "relative", zIndex: 2
  },
  featureIconBlock: {
    width: "150px", height: "150px", borderRadius: "16px",
    border: "2px solid", background: "rgba(255,255,255,0.02)",
    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
    gap: "0.75rem", position: "relative", overflow: "hidden",
    transition: "transform 0.4s cubic-bezier(0.34,1.56,0.64,1), border-color 0.3s, box-shadow 0.3s, background 0.3s",
    transformStyle: "preserve-3d"
  },
  featurePulse: {
    position: "absolute", top: "50%", left: "50%",
    transform: "translate(-50%,-50%)",
    width: "100px", height: "100px", borderRadius: "50%",
    background: "var(--accent-cyan)", opacity: 0.2
  },
  activeIndicator: {
    position: "absolute", bottom: "8px", left: "50%",
    transform: "translateX(-50%)",
    width: "30px", height: "3px", borderRadius: "2px",
    background: "var(--accent-cyan)",
    boxShadow: "0 0 8px var(--accent-cyan)"
  },
  featureLabel: {
    fontSize: "0.78rem", fontWeight: 600, transition: "color 0.3s", zIndex: 2
  },
  detailCard: {
    maxWidth: "520px", width: "100%", padding: "1.5rem",
    borderRadius: "12px", background: "rgba(255,255,255,0.02)",
    border: "1px solid rgba(255,255,255,0.06)", minHeight: "120px",
    position: "relative", overflow: "hidden"
  },
  detailCardContent: { animation: "fadeUp 0.4s ease forwards" },
  transferWidget: {
    maxWidth: "520px", width: "100%", padding: "2rem",
    borderRadius: "16px", background: "rgba(255,255,255,0.02)",
    border: "1px solid rgba(255,255,255,0.06)",
    boxShadow: "0 10px 40px rgba(0,0,0,0.5)"
  },
  transferHeader: {
    display: "flex", justifyContent: "space-between", marginBottom: "1.25rem",
    alignItems: "center"
  },
  packetRow: {
    display: "flex", gap: "0.5rem", marginBottom: "1.25rem"
  },
  packetBlock: {
    flex: 1, height: "50px", borderRadius: "6px",
    border: "1px solid", position: "relative",
    display: "flex", alignItems: "center", justifyContent: "center",
    overflow: "hidden", transition: "border-color 0.3s, background 0.3s"
  },
  progressBarBg: {
    height: "12px", borderRadius: "6px",
    background: "rgba(255,255,255,0.05)", overflow: "hidden",
    marginBottom: "1.25rem", position: "relative"
  },
  progressBarFill: {
    height: "100%", borderRadius: "6px", width: "0%",
    transition: "width 0.1s linear, background 0.3s"
  },
  statusBanner: {
    height: "40px", display: "flex", alignItems: "center", justifyContent: "center"
  },
  techStats: {
    display: "flex", gap: "2rem", marginTop: "1.5rem"
  },
  statItem: {
    display: "flex", alignItems: "center", gap: "0.4rem"
  },
  statValue: {
    fontSize: "0.7rem", fontWeight: 700, color: "#475569",
    letterSpacing: "1px", fontFamily: "monospace"
  },
  matrixBackground: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    opacity: 0.2, overflow: "hidden", display: "flex"
  },
  matrixCol: {
    position: "absolute", display: "flex", flexDirection: "column",
    animation: "rain 4s linear infinite"
  },
  matrixChar: {
    fontSize: "1rem", fontFamily: "monospace", lineHeight: "1.3"
  },
  shieldWrapper: {
    position: "relative", display: "flex", justifyContent: "center", alignItems: "center"
  },
  hexRing: {
    position: "absolute", width: "160px", height: "160px",
    borderRadius: "50%",
    border: "2px solid rgba(0,242,254,0.2)",
    borderTopColor: "var(--accent-cyan)",
    borderRightColor: "transparent"
  },
  hexRing2: {
    position: "absolute", width: "200px", height: "200px",
    borderRadius: "50%",
    border: "1px solid rgba(0,242,254,0.1)",
    borderBottomColor: "var(--accent-cyan)",
    borderLeftColor: "transparent"
  },
  shieldLockCenter: {
    position: "absolute", width: "56px", height: "56px", borderRadius: "50%",
    background: "var(--accent-cyan)",
    display: "flex", alignItems: "center", justifyContent: "center",
    boxShadow: "0 0 20px rgba(0,242,254,0.4)", zIndex: 4
  },
  matrixTitle: {
    fontSize: "1.2rem", fontWeight: 700, color: "#e2e8f0",
    marginTop: "2.5rem", letterSpacing: "2px", textAlign: "center",
    fontFamily: "monospace"
  },
  matrixSubTitle: {
    fontSize: "0.85rem", color: "var(--accent-cyan)", marginTop: "0.5rem",
    letterSpacing: "4px", textTransform: "uppercase"
  },
  outroBlock: {
    display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center",
    position: "relative"
  },
  outroOrb: {
    position: "absolute", width: "300px", height: "300px", borderRadius: "50%",
    background: "radial-gradient(circle, rgba(0,242,254,0.15) 0%, transparent 70%)",
    filter: "blur(20px)", top: "-50px", zIndex: 0
  },
  dividerAccent: {
    width: "80px", height: "3px", background: "var(--accent-cyan)",
    borderRadius: "1.5px", margin: "1rem 0",
    boxShadow: "0 0 10px var(--accent-cyan)"
  },
  outroBadges: {
    display: "flex", gap: "0.5rem", marginTop: "1.5rem", flexWrap: "wrap", justifyContent: "center"
  },
  outroBadge: {
    padding: "0.3rem 0.8rem", borderRadius: "20px",
    background: "rgba(0,242,254,0.08)", border: "1px solid rgba(0,242,254,0.2)",
    fontSize: "0.7rem", fontWeight: 600, color: "var(--accent-cyan)",
    letterSpacing: "1px", fontFamily: "monospace"
  },
  timelineContainer: {
    padding: "1rem 2rem 1.5rem 2rem", display: "flex", flexDirection: "column",
    alignItems: "center", gap: "0.75rem", zIndex: 10,
    background: "rgba(3,7,18,0.8)", backdropFilter: "blur(10px)"
  },
  timelineLabels: {
    display: "flex", gap: "3rem"
  },
  timelineBar: {
    display: "flex", gap: "0.5rem", alignItems: "center"
  },
  timelineDot: {
    height: "6px", borderRadius: "4px", cursor: "pointer",
    transition: "width 0.3s cubic-bezier(0.34,1.56,0.64,1), background-color 0.3s, box-shadow 0.3s"
  }
};
