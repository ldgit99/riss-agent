import { NextRequest, NextResponse } from 'next/server'

const BACKEND = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const jobId    = searchParams.get('jobId')
  const fileType = searchParams.get('fileType')

  if (!jobId || !fileType) {
    return NextResponse.json({ error: 'jobId, fileType 파라미터가 필요합니다.' }, { status: 400 })
  }

  try {
    const res = await fetch(`${BACKEND}/api/download/${jobId}?file_type=${fileType}`)

    if (!res.ok) {
      const body = await res.text().catch(() => '')
      return NextResponse.json(
        { error: `백엔드 오류: ${res.status}`, detail: body },
        { status: res.status }
      )
    }

    const buffer   = await res.arrayBuffer()
    const filename = res.headers.get('content-disposition')?.match(/filename="(.+)"/)?.[1]
                     ?? `${fileType}.csv`

    return new NextResponse(buffer, {
      headers: {
        'Content-Type':        'text/csv; charset=utf-8-sig',
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ error: '다운로드 실패', detail: message }, { status: 500 })
  }
}
