'use client'

import { SSEEvent, SSEProgressEvent, AGENT_LABEL } from '@/lib/types'

interface ProgressPanelProps {
  events: SSEEvent[]
}

export default function ProgressPanel({ events }: ProgressPanelProps) {
  // 에이전트별 최신 progress 추출
  const progressMap: Record<string, SSEProgressEvent> = {}
  const errors: { agent: string; message: string }[] = []

  for (const ev of events) {
    if (ev.type === 'progress') {
      progressMap[ev.agent] = ev
    }
    if (ev.type === 'error') {
      errors.push({ agent: ev.agent, message: ev.message })
    }
  }

  const isDone = events.some(e => e.type === 'done')
  const agents: Array<'riss_hs' | 'riss_hw'> = ['riss_hs', 'riss_hw']

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">수집 진행상황</p>

      {agents.map(agent => {
        const p = progressMap[agent]
        const pct = p && p.total > 0 ? Math.min(100, Math.round((p.count / p.total) * 100)) : 0
        const done = isDone || (p && p.count >= p.total && p.total > 0)

        return (
          <div key={agent} className="space-y-1">
            <div className="flex justify-between text-xs text-gray-600">
              <span className="font-medium">{AGENT_LABEL[agent]}</span>
              <span>
                {p ? `${p.count} / ${p.total}건` : '대기 중'}
                {done && <span className="ml-1 text-green-600 font-bold">✓</span>}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-1.5">
              <div
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  done ? 'bg-green-500' : 'bg-blue-500'
                }`}
                style={{ width: `${done ? 100 : pct}%` }}
              />
            </div>
          </div>
        )
      })}

      {errors.map((err, i) => (
        <p key={i} className="text-xs text-red-500">
          [{AGENT_LABEL[err.agent] ?? err.agent}] 오류: {err.message}
        </p>
      ))}
    </div>
  )
}
