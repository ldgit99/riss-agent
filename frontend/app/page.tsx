'use client'

import { useState, useRef } from 'react'
import SearchForm from '@/components/SearchForm'
import QueryPreview from '@/components/QueryPreview'
import ProgressPanel from '@/components/ProgressPanel'
import ResultTabs from '@/components/ResultTabs'
import { SSEEvent, SSEDoneEvent } from '@/lib/types'

// Next.js 자체 API 라우트로 프록시 → CORS 문제 없음
const API_URL = ''

export default function Home() {
  const [keyword, setKeyword]     = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [events, setEvents]       = useState<SSEEvent[]>([])
  const [doneEvent, setDoneEvent] = useState<SSEDoneEvent | null>(null)
  const readerRef = useRef<ReadableStreamDefaultReader | null>(null)

  const handleSearch = async (kw: string) => {
    readerRef.current?.cancel()
    setIsLoading(true)
    setEvents([])
    setDoneEvent(null)

    try {
      const res = await fetch(`${API_URL}/api/search`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ keyword_raw: kw }),
      })

      if (!res.ok || !res.body) throw new Error(`서버 오류: ${res.status}`)

      const reader  = res.body.getReader()
      readerRef.current = reader
      const decoder = new TextDecoder()
      let buffer    = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const ev: SSEEvent = JSON.parse(line.slice(6))
            setEvents(prev => [...prev, ev])
            if (ev.type === 'done') {
              setDoneEvent(ev)
              setIsLoading(false)
            }
          } catch { /* 빈 줄 무시 */ }
        }
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      setEvents(prev => [...prev, { type: 'error', agent: 'system', message }])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-gray-100 py-10 px-4">
      <div className="mx-auto max-w-2xl space-y-5">

        <div>
          <h1 className="text-2xl font-bold text-gray-900">논문 서지정보 수집기</h1>
          <p className="mt-1 text-sm text-gray-500">
            RISS · KCI 학술/학위 논문 서지정보를 한 번에 수집합니다.
          </p>
        </div>

        <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-200">
          <SearchForm
            value={keyword}
            onChange={setKeyword}
            onSubmit={handleSearch}
            isLoading={isLoading}
          />
        </div>

        {keyword.trim() && <QueryPreview keyword={keyword} />}

        {(isLoading || events.length > 0) && (
          <ProgressPanel events={events} />
        )}

        {doneEvent && (() => {
          const rawTotal  = doneEvent.counts.raw_total
                          ?? (doneEvent.counts.riss_hs + doneEvent.counts.riss_hw + doneEvent.counts.kci)
          const dupCount  = doneEvent.counts.duplicate_count ?? (rawTotal - doneEvent.counts.all)
          return (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-800">
                수집 완료
              </span>
              <span className="text-sm text-gray-600">
                검색된 논문수 <strong className="text-gray-900">{rawTotal}</strong>건
              </span>
              <span className="text-gray-300">·</span>
              <span className="text-sm text-gray-600">
                중복 논문수 <strong className="text-gray-900">{dupCount}</strong>건
              </span>
              <span className="text-gray-300">·</span>
              <span className="text-sm text-gray-600">
                중복 제거 후 총 논문수 <strong className="text-gray-900">{doneEvent.counts.all}</strong>건
              </span>
            </div>
            <ResultTabs
              jobId={doneEvent.job_id}
              counts={doneEvent.counts}
              label={doneEvent.label}
            />
          </div>
          )
        })()}

      </div>
    </main>
  )
}
