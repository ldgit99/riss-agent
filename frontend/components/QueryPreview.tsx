'use client'

import { useEffect, useState } from 'react'
import { parseUserInput, toRissQuery } from '@/lib/queryConverter'

interface QueryPreviewProps {
  keyword: string
}

export default function QueryPreview({ keyword }: QueryPreviewProps) {
  const [riss, setRiss] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => {
      const groups = parseUserInput(keyword)
      setRiss(toRissQuery(groups))
    }, 300)
    return () => clearTimeout(timer)
  }, [keyword])

  if (!riss) return null

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-2 text-sm">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">쿼리 미리보기</p>
      <div className="flex gap-2">
        <span className="w-12 shrink-0 rounded bg-blue-100 px-1.5 py-0.5 text-xs font-bold text-blue-700 text-center">
          RISS
        </span>
        <code className="break-all text-gray-700 text-xs leading-relaxed">{riss}</code>
      </div>
    </div>
  )
}
