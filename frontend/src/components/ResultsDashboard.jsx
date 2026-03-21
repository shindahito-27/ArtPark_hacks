function SkillTable({ title, items }) {
  return (
    <div className="panel">
      <h3>{title}</h3>
      <div className="chips">
        {items.length === 0 && <span className="chip muted">No data</span>}
        {items.map((item) => (
          <div className="skill-row" key={`${title}-${item.name}`}>
            <span>{item.name}</span>
            <span className="badge">{item.gapScore ?? item.score}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ResultsDashboard({ data }) {
  const { overview, skills, insights } = data

  return (
    <section className="results">
      <div className="overview-grid">
        <div className="metric-card">
          <h4>Best Fit Role</h4>
          <p>{overview.bestFitRole}</p>
        </div>
        <div className="metric-card">
          <h4>Role Match Score</h4>
          <p>{overview.bestFitScore}</p>
        </div>
        <div className="metric-card">
          <h4>Target Role</h4>
          <p>{overview.targetRole}</p>
        </div>
      </div>

      <div className="results-grid">
        <SkillTable title="Hard Skill Gaps" items={skills.hard} />
        <SkillTable title="Soft Skill Gaps" items={skills.soft} />
        <SkillTable title="Resume Hard Skills" items={skills.resumeHard} />
        <SkillTable title="Resume Soft Skills" items={skills.resumeSoft} />
      </div>

      <div className="panel">
        <h3>Critical Gaps</h3>
        <div className="chips">
          {insights.criticalGaps.map((item) => (
            <span key={`gap-${item.name}`} className="chip warning">
              {item.name} ({item.gapScore})
            </span>
          ))}
        </div>
      </div>

      <div className="panel">
        <h3>Roadmap Recommendations</h3>
        <div className="roadmap-list">
          {insights.roadmap.map((item) => (
            <article className="roadmap-item" key={`roadmap-${item.skill}`}>
              <strong>{item.skill}</strong>
              <span>{item.phase}</span>
              <p>{item.reason}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

export default ResultsDashboard
