function LoadingState() {
  return (
    <div className="loading-card">
      <div className="spinner" />
      <h3>Pipeline is running</h3>
      <p>Parsing resume, scoring skills, and generating roadmap...</p>
    </div>
  )
}

export default LoadingState
