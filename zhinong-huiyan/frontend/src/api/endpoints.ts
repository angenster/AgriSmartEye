import client, { GATE_TIMEOUT } from './client'
import type {
  AnalysisSummary,
  CostComparison,
  DetectionRecord,
  DetectionResponse,
  DetectionStats,
  DiagnoseResult,
  DiseaseDistribution,
  DroneInfo,
  FieldInfo,
  KnowledgeChunk,
  KnowledgeStats,
  LabelOptions,
  PestInfo,
  QueueStats,
  SampleItem,
  SprayRecord,
  UserInfo,
} from './types'

// ---------------------------------------------------------------- 认证

export async function login(username: string, password: string): Promise<string> {
  // 后端用的是 OAuth2PasswordRequestForm，必须是表单编码
  const body = new URLSearchParams({ username, password })
  const { data } = await client.post<{ access_token: string }>('/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data.access_token
}

export async function register(payload: {
  username: string
  email: string
  password: string
  full_name?: string
}): Promise<UserInfo> {
  const { data } = await client.post<UserInfo>('/auth/register', payload)
  return data
}

export async function fetchMe(): Promise<UserInfo> {
  const { data } = await client.get<UserInfo>('/auth/me')
  return data
}

// ---------------------------------------------------------------- 诊断 Agent

/** 上传图像跑一次诊断 Agent，返回报告与完整思考轨迹 */
export async function diagnose(file: File, fieldId?: number): Promise<DiagnoseResult> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post<DiagnoseResult>('/agent/diagnose', form, {
    params: fieldId != null ? { field_id: fieldId } : undefined,
  })
  return data
}

export async function listAgentRuns(limit = 20) {
  const { data } = await client.get('/agent/runs', { params: { limit } })
  return data
}

export async function getAgentRun(runId: number) {
  const { data } = await client.get(`/agent/runs/${runId}`)
  return data
}

// ---------------------------------------------------------------- 数据飞轮

export async function fetchQueue(status = 'pending', limit = 20, offset = 0): Promise<SampleItem[]> {
  const { data } = await client.get<SampleItem[]>('/review/queue', {
    params: { status, limit, offset },
  })
  return data
}

export async function confirmSample(
  sampleId: number,
  action: 'adopt' | 'correct' | 'reject',
  finalLabel?: string,
  notes?: string,
) {
  const { data } = await client.post(`/review/queue/${sampleId}/confirm`, {
    action,
    final_label: finalLabel,
    notes,
  })
  return data
}

export async function fetchQueueStats(): Promise<QueueStats> {
  const { data } = await client.get<QueueStats>('/review/stats')
  return data
}

export async function fetchLabels(): Promise<LabelOptions> {
  const { data } = await client.get<LabelOptions>('/review/labels')
  return data
}

export async function fetchVersions() {
  const { data } = await client.get('/review/versions')
  return data
}

export async function fetchEvalRuns(limit = 20) {
  const { data } = await client.get('/review/eval-runs', { params: { limit } })
  return data
}

/** 手动跑一次评测门禁。要加载两个权重并在整个评测集上推理，故走独立超时。 */
export async function runGate(payload: {
  candidate_weights: string
  candidate_tag: string
  dataset: string
  base_version?: string
  allow_demo?: boolean
}) {
  const { data } = await client.post('/review/gate', payload, { timeout: GATE_TIMEOUT })
  return data
}

// ---------------------------------------------------------------- 快速识别（非 Agent）

export async function detectUpload(file: File): Promise<DetectionResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post<DetectionResponse>('/detection/upload', form)
  return data
}

export async function fetchDetectionHistory(limit = 20): Promise<DetectionRecord[]> {
  const { data } = await client.get<DetectionRecord[]>('/detection/history', {
    params: { limit },
  })
  return data
}

export async function fetchDetectionStats(): Promise<DetectionStats> {
  const { data } = await client.get<DetectionStats>('/detection/stats')
  return data
}

// ---------------------------------------------------------------- 数据分析

export async function fetchAnalysisSummary(): Promise<AnalysisSummary> {
  const { data } = await client.get<AnalysisSummary>('/analysis/summary')
  return data
}

export async function fetchCostComparison(): Promise<CostComparison[]> {
  const { data } = await client.get<CostComparison[]>('/analysis/cost-comparison')
  return data
}

export async function fetchDiseaseDistribution(): Promise<DiseaseDistribution[]> {
  const { data } = await client.get<DiseaseDistribution[]>('/analysis/disease-distribution')
  return data
}

export async function fetchSprayRecords(limit = 50): Promise<SprayRecord[]> {
  const { data } = await client.get<SprayRecord[]>('/analysis/spray-records', {
    params: { limit },
  })
  return data
}

// ---------------------------------------------------------------- 知识库

export async function fetchPestList(params?: {
  crop_type?: string
  search?: string
}): Promise<PestInfo[]> {
  const { data } = await client.get<PestInfo[]>('/knowledge/', { params })
  return data
}

export async function fetchKnowledgeStats(): Promise<KnowledgeStats> {
  const { data } = await client.get<KnowledgeStats>('/knowledge/stats/overview')
  return data
}

export async function fetchKnowledgeChunks(
  search?: string,
  crop?: string,
  limit = 50,
): Promise<KnowledgeChunk[]> {
  const { data } = await client.get<KnowledgeChunk[]>('/knowledge/chunks', {
    params: { search: search || undefined, crop: crop || undefined, limit },
  })
  return data
}

// ---------------------------------------------------------------- 田块

export async function fetchFields(): Promise<FieldInfo[]> {
  const { data } = await client.get<FieldInfo[]>('/fields/')
  return data
}

export async function createField(payload: {
  name: string
  crop_type: string
  area: number
  location?: string
}): Promise<FieldInfo> {
  const { data } = await client.post<FieldInfo>('/fields/', payload)
  return data
}

// ---------------------------------------------------------------- 无人机

export async function fetchDrones(): Promise<DroneInfo[]> {
  const { data } = await client.get<DroneInfo[]>('/drone/')
  return data
}

export async function sendDroneCommand(
  droneId: string,
  command: 'start' | 'pause' | 'return' | 'emergency',
  variableSpray?: boolean,
) {
  const { data } = await client.post(`/drone/${droneId}/command`, {
    command,
    variable_spray: variableSpray,
  })
  return data
}
