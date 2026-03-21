import { useState } from 'react'
import LoadingState from '../components/LoadingState'
import ResultsDashboard from '../components/ResultsDashboard'
import UploadCard from '../components/UploadCard'

async function analyzeResume({ resumeFile, jdFile }) {
  const formData = new FormData()
  formData.append('file', resumeFile)
  if (jdFile) {
    formData.append('job_description', jdFile)
  }

  const response = await fetch('/api/analyze', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}))
    throw new Error(errorPayload.detail || 'Pipeline failed')
  }
  return response.json()
}

function ResumeAnalyzerPage() {
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [result, setResult] = useState(null)

  const handleAnalyze = async (files) => {
    setIsLoading(true)
    setErrorMessage('')
    try {
      const data = await analyzeResume(files)
      setResult(data)
    } catch (error) {
      setErrorMessage(error.message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <h1>Skillforge</h1>
        <p>Resume Intelligence Dashboard</p>
      </header>

      <UploadCard onAnalyze={handleAnalyze} isLoading={isLoading} />

      {isLoading && <LoadingState />}
      {errorMessage && <div className="error-banner">{errorMessage}</div>}
      {result && <ResultsDashboard data={result} />}
    </main>
  )
}

export default ResumeAnalyzerPage
