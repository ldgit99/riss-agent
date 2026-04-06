import { NextRequest, NextResponse } from 'next/server'

const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const jobId    = searchParams.get('jobId')
  const fileType = searchParams.get('fileType')

  if (!jobId || !fileType) {
    return NextResponse.json({ error: 'jobId, fileType 파라미터가 필요합니다.' }, { status: 400 })
  }

  try {
    const upstream = `${API_URL}/api/download/${jobId}?file_type=${fileType}`
    const res = await fetch(upstream)

    if (!res.ok) {
      return NextResponse.json(
        { error: `백엔드 오류: ${res.status}` },
        { status: res.status }
      )
    }

    const blob     = await res.blob()
    const filename = res.headers.get('content-disposition')?.match(/filename="(.+)"/)?.[1]
                     ?? `${fileType}.csv`

    return new NextResponse(blob, {
      headers: {
        'Content-Type':        'text/csv; charset=utf-8-sig',
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    })
  } catch (err) {
    return NextResponse.json({ error: '다운로드 실패' }, { status: 500 })
  }
}
