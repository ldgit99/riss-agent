import { NextRequest, NextResponse } from 'next/server'

const BACKEND = process.env.API_URL ?? 'http://localhost:8000'

export async function GET(req: NextRequest) {
  const keyword_raw = req.nextUrl.searchParams.get('keyword_raw') ?? ''
  const upstream = await fetch(
    `${BACKEND}/api/preview?keyword_raw=${encodeURIComponent(keyword_raw)}`
  )
  const data = await upstream.json()
  return NextResponse.json(data)
}
