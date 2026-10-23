import client, { GATE_TIMEOUT, TOKEN_KEY } from './client'
import type {
  AgentStep,
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

export interface DiagnoseStreamHandlers {
  onStart?: (data: { image_path?: string }) => void
  onStep?: (step: AgentStep) => void
  onReport?: (result: DiagnoseResult) => void
  onError?: (message: string) => void
}

/**
 * SSE 流式诊断：每完成一步就回调 onStep，前端可实时渲染思考时间线。
 *
 * 用 fetch 而不是 EventSource，因为 EventSource 只支持 GET，无法带 Authorization
 * 头，也无法上传 FormData。
 */
export async function diagnoseStream(
  file: File,
  fieldId: number | undefined,
  handlers: DiagnoseStreamHandlers,
  signal?: AbortSignal,
): Promise<DiagnoseResult | null> {
  const form = new FormData()
  form.append('file', file)
  const token = localStorage.getItem(TOKEN_KEY)
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`

  const query = fieldId != null ? `?field_id=${fieldId}` : ''
  const resp = await fetch(`/api/v1/agent/diagnose/stream${query}`, {
    method: 'POST',
    headers,
    body: form,
    signal,
  })

  if (resp.status === 401) {
    localStorage.removeItem(TOKEN_KEY)
    if (!window.location.pathname.startsWith('/login')) window.location.href = '/login'
    throw new Error('登录已过期，请重新登录')
  }
  if (!resp.ok || !resp.body) {
    let detail = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // 非 JSON 错误体，保留状态码
    }
    throw new Error(detail)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let final: DiagnoseResult | null = null

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const raw = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)

      let event = 'message'
      const dataLines: string[] = []
      for (const line of raw.split(/\r?\n/)) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      if (dataLines.length > 0) {
        const data = JSON.parse(dataLines.join('\n'))
        if (event === 'start') handlers.onStart?.(data)
        else if (event === 'step') handlers.onStep?.(data as AgentStep)
        else if (event === 'report') {
          final = data as DiagnoseResult
          handlers.onReport?.(final)
        } else if (event === 'error') handlers.onError?.(data.message ?? 'Agent 运行失败')
      }
      boundary = buffer.indexOf('\n\n')
    }
  }
  return final
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
