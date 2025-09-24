import React, { useEffect, useState } from 'react'

type ReportContent = {
  prediction: string
  confidence_score: number
  rationale: string
}

type ReportFile = {
  filename: string
  ticker: string
  content: ReportContent
}

type ReportsResponse = {
  date: string
  files: ReportFile[]
  available_dates: string[]
}

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function App() {
  const [reports, setReports] = useState<ReportsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetch(`${API_BASE}/reports`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json()
      })
      .then((data: ReportsResponse) => setReports(data))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6">Loading...</div>
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>
  if (!reports) return <div className="p-6">No reports</div>

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4">Stock Weather AI Reports</h1>
        <p className="text-sm text-gray-600 mb-6">Date: {reports.date}</p>

        <div className="space-y-4">
          {reports.files.map((f) => (
            <div key={f.filename} className="bg-white p-4 rounded shadow">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-lg font-semibold">{f.ticker}</div>
                  <div className="text-sm text-gray-500">{f.filename}</div>
                </div>
                <div className="text-sm font-medium">
                  {f.content.prediction} ({f.content.confidence_score}/10)
                </div>
              </div>
              <div className="mt-2 text-sm text-gray-700">{f.content.rationale}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
