/** 与后端 schemas / 接口响应对应的类型定义 */

export interface UserInfo {
  id: number
  username: string
  email: string
  full_name?: string | null
  organization?: string | null
  role: string
  is_active: boolean
  created_at: string
}

/** 一次 Agent 运行的思考轨迹 */
export interface AgentStep {
  step_no: number
  step_id?: number | null
  thought: string
  tool_name: string
  tool_args?: Record<string, unknown> | null
  ok?: boolean
  result?: unknown
  tool_result?: { ok: boolean; data?: unknown; error?: { code: string; message: string } }
  error?: string | null
  latency_ms?: number | null
}

export interface Evidence {
  type: 'cnn' | 'vlm' | 'rag'
  ref: string
  summary?: string
  quote?: string
  source?: string
  title?: string
  reviewed?: boolean | null
}

export interface Report {
  report_id: string
  run_id: number | null
  field_id: number | null
  image_path: string
  crop: { name: string; confidence: number; source: string }
  disease: {
    name: string
    confidence: number
    source: string
    candidates: { name: string; confidence: number }[]
  }
  severity: { level: string; confidence?: number; basis: string }
  evidence: Evidence[]
  treatment: {
    steps: string[]
    medicines: { name: string; dosage: string; safe_interval_days?: number; source_chunk?: number }[]
    source_chunks?: number[]
    note?: string | null
  }
  needs_human: boolean
  human_review_reason?: string | null
  truncated: boolean
  knowledge_available: boolean
  disclaimer: string
  cost: { vlm_calls: number; llm_tokens: number; latency_ms?: number }
  evidence_valid?: boolean
  evidence_problems?: string[]
  flywheel?: Record<string, unknown> | null
}

export interface DiagnoseResult {
  run_id: number
  status: string
  planner?: string
  steps_used: number
  report: Report
  evidence_valid: boolean
  evidence_problems: string[]
  flywheel?: Record<string, unknown> | null
  steps: AgentStep[]
}

export interface SampleItem {
  sample_id: number
  image_path: string
  source: string
  run_id: number | null
  cnn_top1: string | null
  cnn_conf: number | null
  cnn_topk: { name: string; confidence: number }[] | null
  vlm_pred: string | null
  vlm_conf: number | null
  vlm_rationale: string | null
  trigger_reason: string[]
  status: string
  created_at: string | null
  confirmation: {
    final_label: string | null
    confirm_source: string
    points: number
    notes: string | null
    created_at: string | null
  } | null
}

export interface QueueStats {
  counts: Record<string, number>
  by_trigger_reason: Record<string, number>
  confirmations: number
  corrected_ratio: number | null
  total_points: number
  training_ready_labels: number
}

export interface LabelOptions {
  diseases: string[]
  severities: string[]
  unknown: string
}

// ---------------------------------------------------------------- 识别

export interface DetectionRecord {
  id: number
  image_path: string
  crop_type: string | null
  disease_name: string | null
  confidence: number | null
  severity: string | null
  bbox: number[] | null
  recommendation: string | null
  medicine: string | null
  dosage: string | null
  inference_time: number
  model_version: string
  created_at: string
}

export interface DetectionResponse {
  success: boolean
  data: DetectionRecord[]
  message: string
}

export interface DetectionStats {
  total_detections: number
  today_count: number
  avg_confidence: number
  model_version: string
  is_demo: boolean
}

// ---------------------------------------------------------------- 分析

export interface AnalysisSummary {
  total_detections: number
  total_fields: number
  total_sprayed_area: number
  total_medicine_saved: number
  avg_confidence: number
  monthly_stats: { month: string; detections: number; sprayed_area: number }[]
}

export interface CostComparison {
  month: string
  traditional: number
  smart: number
  saved: number
}

export interface SprayRecord {
  id: number
  field_id: number
  drone_id: string
  area: number
  traditional_usage: number
  actual_usage: number
  saved_percentage: number
  date: string
}

export interface DiseaseDistribution {
  name: string
  value: number
}

// ---------------------------------------------------------------- 知识库 / 田块 / 无人机

export interface PestInfo {
  id: number
  name: string
  crop_type: string
  category: string
  symptoms: string
  causes: string
  prevention: string[]
  treatment: string[]
  severity: string
  season: string[]
  image_count: number
  created_at: string
}

export interface KnowledgeStats {
  total_pests: number
  total_crops: number
  total_images: number
  total_solutions: number
}

/** RAG 索引里的知识条目（系统当前实际使用的知识源） */
export interface KnowledgeChunk {
  id: number
  source: string
  ref_id: string | null
  title: string
  text: string
  metadata: {
    name?: string
    crop?: string
    category?: string
    reviewed?: boolean
  }
  created_at: string
}

export interface FieldInfo {
  id: number
  name: string
  crop_type: string
  area: number
  location: string | null
  latitude: number | null
  longitude: number | null
  status: string
  last_check: string | null
  next_spray: string | null
  created_at: string
  owner_id: number
}

export interface DroneInfo {
  drone_id: string
  name: string
  battery: number
  altitude: number
  speed: number
  spray_rate: number
  latitude: number
  longitude: number
  status: string
  signal: number
  temperature: number
  mission_progress: number
  is_variable_spray: boolean
  updated_at: string
}
