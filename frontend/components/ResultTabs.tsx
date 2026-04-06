'use client'

import { useState } from 'react'
import { FILE_TYPE_LABEL } from '@/lib/types'

interface ResultTabsProps {
  jobId: string
  counts: Record<string, number>
  label: string
}

const TAB_KEYS = ['riss_hs', 'riss_hw', 'kci', 'all'] as const
type TabKey = typeof TAB_KEYS[number]

export default function ResultTabs({ jobId, counts, label }: ResultTabsProps) {
  const [active, setActive] = useState<TabKey>('all')
  const [downloading, setDownloading] = useState<TabKey | null>(null)

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? ''

  const handleDownload = async (fileType: TabKey) => {
    setDownloading(fileType)
    try {
      const res = await fetch(
        `/api/download?jobId=${jobId}&fileType=${fileType}`
      )
      if (!res.ok) {
        const json = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
        throw new Error(json.detail ?? json.error ?? '다운로드 실패')
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${label}_${FILE_TYPE_LABEL[fileType]}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('다운로드 중 오류가 발생했습니다.')
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      {/* 탭 헤더 */}
      <div className="flex border-b border-gray-200 bg-gray-50">
        {TAB_KEYS.map(key => (
          <button
            key={key}
            onClick={() => setActive(key)}
            className={`flex-1 px-3 py-2.5 text-xs font-medium transition-colors duration-150
              ${active === key
                ? 'bg-white text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700'
              }`}
          >
            {FILE_TYPE_LABEL[key]}
            <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-bold
              ${active === key ? 'bg-blue-100 text-blue-600' : 'bg-gray-200 text-gray-500'}`}>
              {counts[key] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {/* 탭 바디 */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm text-gray-600">
            <span className="font-semibold text-gray-900">{counts[active] ?? 0}</span>건 수집됨
          </p>
          <button
            onClick={() => handleDownload(active)}
            disabled={downloading === active || (counts[active] ?? 0) === 0}
            className="rounded-md bg-gray-800 px-3 py-1.5 text-xs font-semibold text-white
                       hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors duration-150 flex items-center gap-1.5"
          >
            {downloading === active ? (
              <>
                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                다운로드 중
              </>
            ) : (
              <>
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                CSV 다운로드
              </>
            )}
          </button>
        </div>

        <p className="text-xs text-gray-400">
          {FILE_TYPE_LABEL[active]} · 파일명: <code className="text-gray-500">{label}_{FILE_TYPE_LABEL[active]}.csv</code>
        </p>
      </div>
    </div>
  )
}
