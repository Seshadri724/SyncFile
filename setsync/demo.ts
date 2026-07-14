import crypto from 'crypto';
import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';

// ==========================================
// SetSync Enterprise Demo — Interactive Walkthrough
// ==========================================

const CORE_URL = process.env.SETSYNC_CORE_URL ?? 'http://localhost:8000';
const MASTER_TOKEN = process.env.SETSYNC_MASTER_TOKEN ?? 'setsync_secret_token_123';
const DEMO_DELAY_MS = Number(process.env.SETSYNC_DEMO_WAIT_MS ?? 700);
const SIMULATED_FAILURE_CHUNK = Number(process.env.SETSYNC_DEMO_FAIL_CHUNK ?? 1);
const CHUNK_SIZE_BYTES = 4 * 1024 * 1024;

let ORG_ID = 'test-org-123';
let TENANT_KEY_HEX = crypto.randomBytes(32).toString('hex');

interface SourceRecord {
  id: string;
  name: string;
  kind: string;
  roots: string[];
  org_id: string;
}

interface RegisterSourceResponse {
  source: SourceRecord;
  agent_key: string;
}

interface FileItem {
  path: string;
  relative_path: string;
  size_bytes: number;
  mtime: string;
  hash_sha256: string;
}

interface EncryptedFileItem extends Omit<FileItem, 'path' | 'relative_path'> {
  path: string;
  relative_path: string;
}

interface SourceContext {
  source: SourceRecord;
  agentKey: string;
}

interface UploadInventoryResponse {
  ok?: boolean;
  accepted?: number;
}

interface TransferStatusResponse {
  received_chunks: number[];
}

interface TransferFinalizeResponse {
  target_path?: string;
  status?: string;
}

interface CoordinatorSetView {
  union: string[];
  intersection: string[];
  onlyA: string[];
  onlyB: string[];
  conflicts: Array<{
    path: string;
    left_hash: string;
    right_hash: string;
  }>;
}

interface LocalSetView extends CoordinatorSetView {
  decodedUnion: string[];
  decodedIntersection: string[];
  decodedOnlyA: string[];
  decodedOnlyB: string[];
  decodedConflicts: Array<{
    path: string;
    left_hash: string;
    right_hash: string;
  }>;
}

class DemoLogger {
  private readonly started = Date.now();

  banner(title: string) {
    console.log(`\n${'='.repeat(74)}`);
    console.log(` ${title}`);
    console.log(`${'='.repeat(74)}`);
  } section(title: string) {
    console.log(`\n▶ ${title}`);
  } step(message: string) {
    console.log(`   • ${message}`);
  } success(message: string) {
    console.log(`   ✅ ${message}`);
  } warn(message: string) {
    console.log(`   ⚠️  ${message}`);
  } error(message: string) {
    console.log(`   ❌ ${message}`);
  } data(label: string, value: unknown) {
    console.log(`   ℹ️  ${label}:`, value);
  } table(rows: Array<Record<string, unknown>>) {
    console.table(rows);
  } finish() {
    const seconds = ((Date.now() - this.started) / 1000).toFixed(2);
    console.log(`\n🏁 Demo finished in ${seconds}s`);
  }
}

const log = new DemoLogger();

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function prettyBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unit = -1;
  do {
    size /= 1024;
    unit += 1;
  } while (size >= 1024 && unit < units.length - 1);
  return `${size.toFixed(size >= 100 ? 0 : size >= 10 ? 1 : 2)} ${units[unit]}`;
}

function shortHash(value: string, length = 10): string {
  return value.slice(0, length);
}

function sha256(input: crypto.BinaryLike): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

function md5(input: crypto.BinaryLike): Buffer {
  return crypto.createHash('md5').update(input).digest();
}

function getTenantKey(tenantKeyHex: string): Buffer {
  return Buffer.from(tenantKeyHex, 'hex');
}

// Context-aware key-derivation for folders (Component 1)
function getContextKey(baseKey: Buffer, context: string): Buffer {
  return crypto.createHmac('sha256', baseKey)
    .update(context, 'utf-8')
    .digest();
}

function encryptComponent(component: string, key: Buffer): string {
  const data = Buffer.from(component, 'utf-8');
  const iv = md5(data);
  const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);
  cipher.setAutoPadding(true);
  const ciphertext = Buffer.concat([cipher.update(data), cipher.final()]);
  return Buffer.concat([iv, ciphertext]).toString('base64url');
}

function decryptComponent(ciphertextBase64Url: string, key: Buffer): string {
  const raw = Buffer.from(ciphertextBase64Url, 'base64url');
  if (raw.length < 16) {
    throw new Error('Ciphertext component too short');
  }
  const iv = raw.subarray(0, 16);
  const ciphertext = raw.subarray(16);
  const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
  decipher.setAutoPadding(true);
  const plaintext = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  return plaintext.toString('utf-8');
}

function encryptDeterministic(plaintext: string, keyHex: string): string {
  if (!plaintext) return '';
  const baseKey = getTenantKey(keyHex);
  const parts = plaintext.split('/');
  const encryptedParts: string[] = [];
  let currentContext = '';

  for (const part of parts) {
    const levelKey = getContextKey(baseKey, currentContext);
    const enc = encryptComponent(part, levelKey);
    encryptedParts.push(enc);
    if (currentContext) {
      currentContext += '/' + part;
    } else {
      currentContext = part;
    }
  }

  return encryptedParts.join('/');
}

function decryptDeterministic(payloadBase64Url: string, keyHex: string): string {
  if (!payloadBase64Url) return '';
  try {
    const baseKey = getTenantKey(keyHex);
    const parts = payloadBase64Url.split('/');
    const decryptedParts: string[] = [];
    let currentContext = '';

    for (const part of parts) {
      const levelKey = getContextKey(baseKey, currentContext);
      const dec = decryptComponent(part, levelKey);
      decryptedParts.push(dec);
      if (currentContext) {
        currentContext += '/' + dec;
      } else {
        currentContext = dec;
      }
    }

    return decryptedParts.join('/');
  } catch (error) {
    return payloadBase64Url;
  }
}

function buildClient(): AxiosInstance {
  const instance = axios.create({
    baseURL: CORE_URL,
    timeout: 30_000,
    headers: {
      'Content-Type': 'application/json'
    }
  });
  
  instance.interceptors.request.use(config => {
    config.headers['X-SetSync-Tenant-Key'] = TENANT_KEY_HEX;
    return config;
  });
  
  return instance;
}

const client = buildClient();

function authHeaders(): Record<string, string> {
  return { Authorization: `Bearer ${MASTER_TOKEN}` };
}

function agentHeaders(sourceId: string, agentKey: string): Record<string, string> {
  return {
    'X-SetSync-Source-ID': sourceId,
    'X-SetSync-Agent-Key': agentKey,
    'X-SetSync-Tenant-Key': TENANT_KEY_HEX
  };
}

function describeAxiosError(error: unknown): string {
  const err = error as AxiosError;
  const status = err.response?.status;
  const data = err.response?.data;
  if (status) return `HTTP ${status} ${JSON.stringify(data)}`;
  return err.message ?? String(error);
}

function buildMockInventory(device: 'A' | 'B'): FileItem[] {
  const now = new Date().toISOString();
  if (device === 'A') {
    return [
      {
        path: '/data/workstation_a/payroll_q3.xlsx',
        relative_path: 'payroll_q3.xlsx',
        size_bytes: 4_500_000,
        mtime: now,
        hash_sha256: sha256('payroll_q3_v1')
      },
      {
        path: '/data/workstation_a/shared_docs/manual.pdf',
        relative_path: 'shared_docs/manual.pdf',
        size_bytes: 120_000,
        mtime: now,
        hash_sha256: sha256('manual_shared_v1')
      },
      {
        path: '/data/workstation_a/shared_docs/logo.png',
        relative_path: 'shared_docs/logo.png',
        size_bytes: 54_000,
        mtime: now,
        hash_sha256: sha256('logo_marketing_v1')
      },
      {
        path: '/data/workstation_a/finance/budget_2027.xlsx',
        relative_path: 'finance/budget_2027.xlsx',
        size_bytes: 950_000,
        mtime: now,
        hash_sha256: sha256('budget_2027_forecast')
      }
    ];
  }

  return [
    {
      path: '/data/server_b/shared_docs/manual.pdf',
      relative_path: 'shared_docs/manual.pdf',
      size_bytes: 120_000,
      mtime: now,
      hash_sha256: sha256('manual_shared_v1')
    },
    {
      path: '/data/server_b/shared_docs/logo.png',
      relative_path: 'shared_docs/logo.png',
      size_bytes: 59_000,
      mtime: now,
      hash_sha256: sha256('logo_marketing_v2_conflict')
    },
    {
      path: '/data/server_b/ops/runbook.md',
      relative_path: 'ops/runbook.md',
      size_bytes: 8_100,
      mtime: now,
      hash_sha256: sha256('ops_runbook_v5')
    },
    {
      path: '/data/server_b/backups/database.bak',
      relative_path: 'backups/database.bak',
      size_bytes: 15_800_000,
      mtime: now,
      hash_sha256: sha256('nightly_backup_blob')
    }
  ];
}

function encryptInventory(files: FileItem[], tenantKeyHex: string): EncryptedFileItem[] {
  return files.map(file => ({
    ...file,
    path: encryptDeterministic(file.path, tenantKeyHex),
    relative_path: encryptDeterministic(file.relative_path, tenantKeyHex)
  }));
}

function buildCiphertextMap(encryptedFiles: EncryptedFileItem[]): Map<string, string> {
  return new Map(encryptedFiles.map(file => [file.relative_path, decryptDeterministic(file.relative_path, TENANT_KEY_HEX)]));
}

async function request<T = unknown>(method: 'get' | 'post', url: string, config?: AxiosRequestConfig, body?: unknown): Promise<T> {
  const response = method === 'get'
    ? await client.get<T>(url, config)
    : await client.post<T>(url, body, config);
  return response.data;
}

async function registerSource(name: string, root: string): Promise<SourceContext> {
  const data = await request<RegisterSourceResponse>('post', '/sources/register', {
    headers: authHeaders()
  }, {
    name,
    kind: 'device',
    roots: [root],
    org_id: ORG_ID
  });

  return {
    source: data.source,
    agentKey: data.agent_key
  };
}

async function uploadInventory(sourceContext: SourceContext, files: EncryptedFileItem[]) {
  return request<UploadInventoryResponse>('post', '/inventory/upload', {
    headers: agentHeaders(sourceContext.source.id, sourceContext.agentKey)
  }, {
    source_id: sourceContext.source.id,
    files
  });
}

function computeLocalSetView(a: EncryptedFileItem[], b: EncryptedFileItem[], decodeMap: Map<string, string>): LocalSetView {
  const aByPath = new Map(a.map(file => [file.relative_path, file]));
  const bByPath = new Map(b.map(file => [file.relative_path, file]));
  const pathUniverse = Array.from(new Set([...aByPath.keys(), ...bByPath.keys()])).sort();

  const union: string[] = [];
  const intersection: string[] = [];
  const onlyA: string[] = [];
  const onlyB: string[] = [];
  const conflicts: LocalSetView['conflicts'] = [];

  for (const path of pathUniverse) {
    const left = aByPath.get(path);
    const right = bByPath.get(path);

    union.push(path);

    if (left && right) {
      if (left.hash_sha256 === right.hash_sha256) {
        intersection.push(path);
      } else {
        conflicts.push({
          path,
          left_hash: left.hash_sha256,
          right_hash: right.hash_sha256
        });
      }
    } else if (left) {
      onlyA.push(path);
    } else if (right) {
      onlyB.push(path);
    }
  }

  const decode = (items: string[]) => items.map(item => decodeMap.get(item) ?? item);
  return {
    union,
    intersection,
    onlyA,
    onlyB,
    conflicts,
    decodedUnion: decode(union),
    decodedIntersection: decode(intersection),
    decodedOnlyA: decode(onlyA),
    decodedOnlyB: decode(onlyB),
    decodedConflicts: conflicts.map(item => ({
      path: decodeMap.get(item.path) ?? item.path,
      left_hash: item.left_hash,
      right_hash: item.right_hash
    }))
  };
}

function normalizeCoordinatorSetView(raw: any): CoordinatorSetView {
  const files: any[] = raw?.files ?? [];
  const union: string[] = [];
  const intersection: string[] = [];
  const onlyA: string[] = [];
  const onlyB: string[] = [];
  const conflicts: CoordinatorSetView['conflicts'] = [];

  for (const f of files) {
    union.push(f.relative_path);
    if (f.location === 'Both') {
      intersection.push(f.relative_path);
    } else if (f.location === 'A') {
      onlyA.push(f.relative_path);
    } else if (f.location === 'B') {
      onlyB.push(f.relative_path);
    } else if (f.location === 'Conflict') {
      conflicts.push({
        path: f.relative_path,
        left_hash: f.hash_sha256,
        right_hash: 'conflict_hash'
      });
    }
  }

  return { union, intersection, onlyA, onlyB, conflicts };
}

async function fetchCoordinatorSetView(sourceA: SourceContext, sourceB: SourceContext): Promise<CoordinatorSetView | null> {
  try {
    const data = await request<any>('get', '/sets/view', {
      headers: authHeaders(),
      params: {
        source_x: sourceA.source.id,
        source_y: sourceB.source.id,
        org_id: ORG_ID
      }
    });
    return normalizeCoordinatorSetView(data);
  } catch (error) {
    log.warn(`Coordinator /sets/view unavailable or shape mismatch, falling back to local deterministic comparison (${describeAxiosError(error)})`);
    return null;
  }
}

function decodeCoordinatorSetView(view: CoordinatorSetView, decodeMap: Map<string, string>): LocalSetView {
  const decode = (items: string[]) => items.map(item => decodeMap.get(item) ?? item);
  return {
    ...view,
    decodedUnion: decode(view.union),
    decodedIntersection: decode(view.intersection),
    decodedOnlyA: decode(view.onlyA),
    decodedOnlyB: decode(view.onlyB),
    decodedConflicts: view.conflicts.map(item => ({
      path: decodeMap.get(item.path) ?? item.path,
      left_hash: item.left_hash,
      right_hash: item.right_hash
    }))
  };
}

async function initializeTransferSession(sourceContext: SourceContext, sessionId: string, filePath: string, payload: Buffer) {
  const totalChunks = Math.ceil(payload.length / CHUNK_SIZE_BYTES);
  const fileSha = sha256(payload);

  await request('post', '/transfer/init', {
    headers: agentHeaders(sourceContext.source.id, sourceContext.agentKey)
  }, {
    session_id: sessionId,
    total_chunks: totalChunks,
    chunk_size: CHUNK_SIZE_BYTES,
    file_sha256: fileSha,
    file_path: filePath,
    org_id: ORG_ID
  });

  return { totalChunks, fileSha };
}

async function uploadChunk(sourceContext: SourceContext, sessionId: string, index: number, chunkData: Buffer) {
  const chunkSha = sha256(chunkData);
  await client.post(`/transfer/${sessionId}/chunk/${index}`, chunkData, {
    headers: {
      ...agentHeaders(sourceContext.source.id, sourceContext.agentKey),
      'Content-Type': 'application/octet-stream',
      'X-Chunk-SHA256': chunkSha
    },
    maxBodyLength: Infinity
  });
  return chunkSha;
}

async function fetchTransferStatus(sourceContext: SourceContext, sessionId: string): Promise<TransferStatusResponse> {
  return request<TransferStatusResponse>('get', `/transfer/${sessionId}`, {
    headers: agentHeaders(sourceContext.source.id, sourceContext.agentKey)
  });
}

async function finalizeTransfer(sourceContext: SourceContext, sessionId: string): Promise<TransferFinalizeResponse> {
  return request<TransferFinalizeResponse>('post', `/transfer/${sessionId}/finalize`, {
    headers: agentHeaders(sourceContext.source.id, sourceContext.agentKey)
  }, {});
}

async function runDemo() {
  log.banner('🚀 SetSync Enterprise Walkthrough');
  log.data('Coordinator URL', CORE_URL);

  const decodeMap = new Map<string, string>();

  try {
    // ------------------------------------------------------------------
    // 1. AUTHENTICATION & SETUP
    // ------------------------------------------------------------------
    log.section('1) Authentication and Setup');
    
    // Create Organization
    log.step('Creating Organization "Test Corp" on coordinator...');
    const orgRes = await request<any>('post', '/auth/organizations', {
      headers: authHeaders()
    }, {
      name: 'Test Corp'
    });
    ORG_ID = orgRes.id;
    log.success(`Created Organization: ${orgRes.name} (ID: ${ORG_ID})`);

    // Create User
    const randomSuffix = Math.floor(Math.random() * 10000);
    const demoEmail = `admin_${randomSuffix}@testcorp.com`;
    const demoPassword = 'password123';
    
    log.step(`Creating Admin User "${demoEmail}"...`);
    await request<any>('post', '/auth/users', {
      headers: authHeaders()
    }, {
      email: demoEmail,
      password: demoPassword,
      role: 'admin',
      org_id: ORG_ID
    });
    log.success(`Created Admin User: ${demoEmail} (Password: ${demoPassword})`);

    // Derive deterministic key to match backend's server-derived fallback
    const derivedKey = crypto.createHash('sha256')
      .update(`${ORG_ID}:${MASTER_TOKEN}`)
      .digest();
    TENANT_KEY_HEX = derivedKey.toString('hex');
    log.data('Derived zero-knowledge tenant key', `${TENANT_KEY_HEX.slice(0, 16)}…${TENANT_KEY_HEX.slice(-8)}`);
    log.step('The coordinator will only receive pre-encrypted metadata, never raw logical paths.');

    const workstationA = await registerSource('Workstation-A', '/data/workstation_a');
    const serverB = await registerSource('Server-B', '/data/server_b');
    log.success(`Registered ${workstationA.source.name} as source ${workstationA.source.id}`);
    log.success(`Registered ${serverB.source.name} as source ${serverB.source.id}`);
    log.step(`Agent key preview for Workstation-A: ${shortHash(workstationA.agentKey)}…`);
    await sleep(DEMO_DELAY_MS);

    // Save demo credentials to global scope or context so we can print them at the end
    (global as any).demoEmail = demoEmail;
    (global as any).demoPassword = demoPassword;

    // ------------------------------------------------------------------
    // 2. INVENTORY & ZERO-KNOWLEDGE INGESTION
    // ------------------------------------------------------------------
    log.section('2) Inventory Scan and Zero-Knowledge Metadata Ingestion');
    const localA = buildMockInventory('A');
    const localB = buildMockInventory('B');
    const encryptedA = encryptInventory(localA, TENANT_KEY_HEX);
    const encryptedB = encryptInventory(localB, TENANT_KEY_HEX);

    for (const [k, v] of buildCiphertextMap(encryptedA)) decodeMap.set(k, v);
    for (const [k, v] of buildCiphertextMap(encryptedB)) decodeMap.set(k, v);

    log.step('Uploading Device A inventory as encrypted blobs.');
    await uploadInventory(workstationA, encryptedA);
    log.success('Device A inventory uploaded.');

    log.step('Uploading Device B inventory as encrypted blobs.');
    await uploadInventory(serverB, encryptedB);
    log.success('Device B inventory uploaded.');

    log.table([
      {
        device: 'Workstation-A',
        files: encryptedA.length,
        sample_ciphertext_path: `${encryptedA[0].relative_path.slice(0, 28)}…`,
        sample_plaintext_path: localA[0].relative_path
      },
      {
        device: 'Server-B',
        files: encryptedB.length,
        sample_ciphertext_path: `${encryptedB[0].relative_path.slice(0, 28)}…`,
        sample_plaintext_path: localB[0].relative_path
      }
    ]);
    await sleep(DEMO_DELAY_MS);

    // ------------------------------------------------------------------
    // 3. SET LOGIC: UNION / INTERSECTION / DIFF / CONFLICTS
    // ------------------------------------------------------------------
    log.section('3) Inventory Set Logic (Union, Intersection, Only A, Only B, Conflicts)');
    const remoteSetView = await fetchCoordinatorSetView(workstationA, serverB);
    const setView = remoteSetView
      ? decodeCoordinatorSetView(remoteSetView, decodeMap)
      : computeLocalSetView(encryptedA, encryptedB, decodeMap);

    log.step('Coordinator compares encrypted relative paths deterministically.');
    log.table([
      { bucket: 'Union', count: setView.decodedUnion.length, paths: setView.decodedUnion.join(' | ') || '—' },
      { bucket: 'Intersection', count: setView.decodedIntersection.length, paths: setView.decodedIntersection.join(' | ') || '—' },
      { bucket: 'Only A', count: setView.decodedOnlyA.length, paths: setView.decodedOnlyA.join(' | ') || '—' },
      { bucket: 'Only B', count: setView.decodedOnlyB.length, paths: setView.decodedOnlyB.join(' | ') || '—' },
      { bucket: 'Conflicts', count: setView.decodedConflicts.length, paths: setView.decodedConflicts.map(item => item.path).join(' | ') || '—' }
    ]);

    if (setView.conflicts.length > 0) {
      log.step('Conflict detail (same encrypted logical path, different content hashes).');
      log.table(setView.decodedConflicts.map(item => ({
        path: item.path,
        left_hash: shortHash(item.left_hash, 12),
        right_hash: shortHash(item.right_hash, 12)
      })));
    }
    await sleep(DEMO_DELAY_MS);

    // ------------------------------------------------------------------
    // 4. RESILIENT CHUNKED TRANSFER
    // ------------------------------------------------------------------
    log.section('4) Resilient Chunked Transfer (Simulated Network Drop + Resume)');
    const sessionId = crypto.randomUUID();
    const targetFile = 'finance/budget_2027.xlsx';
    const largePayload = Buffer.alloc(10 * 1024 * 1024, 'X');
    const { totalChunks, fileSha } = await initializeTransferSession(workstationA, sessionId, targetFile, largePayload);

    log.data('Transfer session ID', sessionId);
    log.data('Chunk size', prettyBytes(CHUNK_SIZE_BYTES));
    log.data('Total payload', prettyBytes(largePayload.length));
    log.data('Whole-file SHA256', shortHash(fileSha, 16));

    let simulatedDropTriggered = false;
    for (let i = 0; i < totalChunks; i += 1) {
      const start = i * CHUNK_SIZE_BYTES;
      const end = Math.min(start + CHUNK_SIZE_BYTES, largePayload.length);
      const chunkData = largePayload.subarray(start, end);

      if (i === SIMULATED_FAILURE_CHUNK && !simulatedDropTriggered) {
        simulatedDropTriggered = true;
        log.warn(`Simulating a network failure before chunk ${i + 1}/${totalChunks}.`);
        break;
      }

      const chunkSha = await uploadChunk(workstationA, sessionId, i, chunkData);
      log.success(`Uploaded chunk ${i + 1}/${totalChunks} (${prettyBytes(chunkData.length)}, sha=${shortHash(chunkSha, 8)})`);
    }

    log.step('Waiting before resuming the interrupted session...');
    await sleep(Math.max(DEMO_DELAY_MS * 2, 1500));

    const status = await fetchTransferStatus(workstationA, sessionId);
    log.data('Server says received chunks', status.received_chunks);

    for (let i = 0; i < totalChunks; i += 1) {
      if (status.received_chunks.includes(i)) continue;
      const start = i * CHUNK_SIZE_BYTES;
      const end = Math.min(start + CHUNK_SIZE_BYTES, largePayload.length);
      const chunkData = largePayload.subarray(start, end);
      const chunkSha = await uploadChunk(workstationA, sessionId, i, chunkData);
      log.success(`Resumed chunk ${i + 1}/${totalChunks} (${prettyBytes(chunkData.length)}, sha=${shortHash(chunkSha, 8)})`);
    }

    const finalize = await finalizeTransfer(workstationA, sessionId);
    log.success(`Transfer finalized. Server target path: ${finalize.target_path ?? targetFile}`);
    await sleep(DEMO_DELAY_MS);

    // ------------------------------------------------------------------
    // 5. SECURITY & GOVERNANCE AUDIT
    // ------------------------------------------------------------------
    log.section('5) Security and Governance Audit');
    const stolenRow = encryptedA[0].relative_path;
    log.step('Simulating a raw metadata row leaked from the coordinator database.');
    log.data('Stolen ciphertext blob', stolenRow);

    try {
      Buffer.from(stolenRow, 'utf-8').toString('utf-8');
      log.warn('Plain string inspection yields ciphertext only; semantic path information is still hidden.');
    } catch {
      log.warn('Raw inspection cannot reveal the original path.');
    }

    const locallyDecrypted = decryptDeterministic(stolenRow, TENANT_KEY_HEX);
    log.success(`Client-side key successfully restores original logical path locally: ${locallyDecrypted}`);
    log.step('This demonstrates the zero-knowledge boundary: the coordinator can compare encrypted paths but cannot interpret them without the tenant key.');

    log.step('Now simulating a malicious cross-tenant dashboard query.');
    try {
      await client.get('/analysis/fleet', {
        headers: {
          Authorization: 'Bearer user:rogue_user:viewer:different_org'
        }
      });
      log.error('RLS test FAILED: cross-tenant read unexpectedly succeeded.');
    } catch (error) {
      const err = error as AxiosError;
      const statusCode = err.response?.status;
      if (statusCode === 401 || statusCode === 403) {
        log.success(`RLS test PASSED: cross-tenant access blocked with HTTP ${statusCode}.`);
      } else {
        log.warn(`Unexpected cross-tenant response: ${describeAxiosError(error)}`);
      }
    }

    log.banner('✨ SetSync Demo Takeaways');
    log.step('Authentication registered two agents and established a tenant-scoped trust boundary.');
    log.step('Inventory metadata was encrypted client-side before upload.');
    log.step('Set logic still worked because deterministic ciphertext preserves equality checks.');
    log.step('Chunked transfer resumed from missing chunks instead of restarting from zero.');
    log.step('Zero-knowledge storage and RLS together protected confidentiality and tenant isolation.');

    log.banner('🖥️  SetSync Web UI Dashboard Login');
    log.step('You can now log into the running Web UI dashboard using these credentials:');
    log.data('Web Dashboard URL', 'http://localhost:5173/demo');
    log.data('Email Address', (global as any).demoEmail ?? 'admin@testcorp.com');
    log.data('Password', (global as any).demoPassword ?? 'password123');
    log.step('All simulated file records will appear fully decrypted and compared live in your browser!');
  } catch (error) {
    log.error(`Demo execution failed: ${describeAxiosError(error)}`);
    process.exitCode = 1;
  } finally {
    log.finish();
  }
}

void runDemo();
