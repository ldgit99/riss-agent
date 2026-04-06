import { NextRequest } from 'next/server'

const BACKEND = process.env.API_URL ?? 'http://localhost:8000'

// Railway 백엔드로 SSE 스트림을 서버 사이드에서 프록시
// → 브라우저 CORS 문제 완전히 우회
export async function POST(req: NextRequest) {
  const body = await req.json()

  const upstream = await fetch(`${BACKEND}/api/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!upstream.ok || !upstream.body) {
    return new Response(
      JSON.stringify({ error: `Backend error: ${upstream.status}` }),
      { status: upstream.status, headers: { 'Content-Type': 'application/json' } }
    )
  }

  return new Response(upstream.body, {
    headers: {
      'Content-Type':      'text/event-stream',
      'Cache-Control':     'no-cache',
      'X-Accel-Buffering': 'no',
    },
  })
}
