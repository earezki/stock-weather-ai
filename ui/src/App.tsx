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

function formatRationale(text: string) {
  // split into sentences by dot followed by space (keep the dot)
  const parts = text.split(/\.\s+/).filter(Boolean)
  return (
    <div className="space-y-3">
      {parts.map((p, i) => (
        <p key={i} className="whitespace-pre-wrap">
          {p.trim() + (p.endsWith('.') ? '' : '.')}
        </p>
      ))}
    </div>
  )
}

export default function App() {
  const [reports, setReports] = useState<ReportsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [expandedFile, setExpandedFile] = useState<ReportFile | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [sortOption, setSortOption] = useState<string>('ticker-asc')

  const fetchReports = (date?: string | null) => {
    setLoading(true)
    setError(null)
    const url = date ? `${API_BASE}/reports?date=${encodeURIComponent(date)}` : `${API_BASE}/reports`
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json()
      })
      .then((data: ReportsResponse) => {
        setReports(data)
        setSelectedDate(data.date)
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchReports(null)
  }, [])

  useEffect(() => {
    if (selectedDate) {
      fetchReports(selectedDate)
    }
  }, [selectedDate])
  const visibleFiles = React.useMemo(() => {
    if (!reports) return [] as ReportFile[]
    const q = searchQuery.trim().toLowerCase()
    let list = reports.files.filter((f) => {
      if (!q) return true
      // filter by ticker (primary) but also match filename or rationale
      return (
        f.ticker.toLowerCase().includes(q) ||
        f.filename.toLowerCase().includes(q) ||
        f.content.rationale.toLowerCase().includes(q)
      )
    })

    const compare = (a: ReportFile, b: ReportFile) => {
      switch (sortOption) {
        case 'ticker-asc':
          return a.ticker.localeCompare(b.ticker)
        case 'ticker-desc':
          return b.ticker.localeCompare(a.ticker)
        case 'confidence-asc':
          return a.content.confidence_score - b.content.confidence_score
        case 'confidence-desc':
          return b.content.confidence_score - a.content.confidence_score
        case 'prediction':
          return a.content.prediction.localeCompare(b.content.prediction)
        default:
          return 0
      }
    }

    list.sort(compare)
    return list
  }, [reports, searchQuery, sortOption])

  if (loading) return <div className="p-6">Loading...</div>
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>
  if (!reports) return <div className="p-6">No reports</div>

  const onDateChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value || null
    setExpandedFile(null)
    setSelectedDate(v)
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <div className="max-w-6xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold">Stock Weather AI Reports</h1>
              <p className="text-sm text-gray-600">Date: {reports.date}</p>
            </div>
            <div>
              <label className="text-sm text-gray-600 mr-2">Select date</label>
              <select
                value={selectedDate ?? ''}
                onChange={onDateChange}
                className="border rounded px-2 py-1"
              >
                <option value="">Latest</option>
                {reports.available_dates.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mb-4 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <input
              placeholder="Search by ticker, filename or text..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="border rounded px-3 py-2 flex-1 min-w-0"
            />
            <select
              value={sortOption}
              onChange={(e) => setSortOption(e.target.value)}
              className="border rounded px-2 py-2 w-full sm:w-auto"
            >
              <option value="ticker-asc">Ticker ↑</option>
              <option value="ticker-desc">Ticker ↓</option>
              <option value="confidence-desc">Confidence ↓</option>
              <option value="confidence-asc">Confidence ↑</option>
              <option value="prediction">Prediction</option>
            </select>
          </div>

          <div className="space-y-4">
            {visibleFiles.map((f) => (
              <div
                key={f.filename}
                className="bg-white p-4 rounded shadow cursor-pointer"
                onClick={() => setExpandedFile(f)}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-lg font-semibold">{f.ticker}</div>
                    <div className="text-sm text-gray-500">{f.filename}</div>
                  </div>
                  <div className="text-sm font-medium">
                    {f.content.prediction} ({f.content.confidence_score}/10)
                  </div>
                </div>
                <div className="mt-2 text-sm text-gray-700 line-clamp-3">{f.content.rationale}</div>
              </div>
            ))}
          </div>
        </div>

        <aside className="bg-white p-6 rounded shadow lg:col-span-2">
          {expandedFile ? (
            <div>
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-lg font-bold">{expandedFile.ticker}</div>
                  <div className="text-sm text-gray-500">{expandedFile.filename}</div>
                </div>
                <div>
                  <button
                    onClick={() => setExpandedFile(null)}
                    className="text-sm text-gray-500 hover:text-gray-700"
                  >
                    Close
                  </button>
                </div>
              </div>

              <div className="mt-3">
                <div className="text-sm text-gray-600 mb-2">Prediction</div>
                <div className="font-medium mb-2">
                  {expandedFile.content.prediction} ({expandedFile.content.confidence_score}/10)
                </div>
                <div className="text-sm text-gray-600 mb-1">Rationale</div>
                <div className="text-sm bg-gray-50 p-4 rounded overflow-auto">
                  {formatRationale(expandedFile.content.rationale)}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-gray-600">Select a file to see details</div>
          )}
        </aside>
      </div>
    </div>
  )
}
