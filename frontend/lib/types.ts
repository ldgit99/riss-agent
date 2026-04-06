export type SSEEventType = 'query' | 'progress' | 'done' | 'error'

export interface SSEQueryEvent {
  type: 'query'
  riss: string
  kci: string
}

export interface SSEProgressEvent {
  type: 'progress'
  agent: string
  count: number
  total: number
}

export interface SSEDoneEvent {
  type: 'done'
  job_id: string
  label: string
  counts: {
    riss_hs: number
    riss_hw: number
    all: number
    raw_total: number
    duplicate_count: number
  }
  files: Record<string, string>
}

export interface SSEErrorEvent {
  type: 'error'
  agent: string
  message: string
}

export type SSEEvent = SSEQueryEvent | SSEProgressEvent | SSEDoneEvent | SSEErrorEvent

export const AGENT_LABEL: Record<string, string> = {
  riss_hs: 'RISS 학술논문',
  riss_hw: 'RISS 학위논문',
}

export const FILE_TYPE_LABEL: Record<string, string> = {
  riss_hs: 'RISS 학술논문',
  riss_hw: 'RISS 학위논문',
  all:     '전체 통합',
}
