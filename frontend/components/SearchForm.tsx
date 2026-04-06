'use client'

interface SearchFormProps {
  onSubmit: (keyword: string) => void
  onChange: (keyword: string) => void
  isLoading: boolean
  value: string
}

export default function SearchForm({ onSubmit, onChange, isLoading, value }: SearchFormProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (value.trim()) onSubmit(value.trim())
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label htmlFor="keyword" className="block text-sm font-medium text-gray-700 mb-1">
          검색어
        </label>
        <textarea
          id="keyword"
          rows={3}
          className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                     resize-none font-mono"
          placeholder={
            '단일:  인공지능\nOR:    생성형AI, ChatGPT, 챗GPT\nAND:   생성형AI,ChatGPT / 인공지능,AI / 교육,수업'
          }
          value={value}
          onChange={e => onChange(e.target.value)}
          disabled={isLoading}
        />
        <p className="mt-1 text-xs text-gray-400">
          <span className="font-semibold">/</span> 로 AND 그룹 구분 &nbsp;·&nbsp;
          <span className="font-semibold">,</span> 로 OR 키워드 구분
        </p>
      </div>

      <button
        type="submit"
        disabled={isLoading || !value.trim()}
        className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white
                   hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                   transition-colors duration-150"
      >
        {isLoading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            수집 중...
          </span>
        ) : '수집 시작'}
      </button>
    </form>
  )
}
