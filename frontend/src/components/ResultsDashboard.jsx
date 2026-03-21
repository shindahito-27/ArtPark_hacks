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

const STATUS_COLORS = {
  known: '#22c55e',
  next_step: '#facc15',
  missing: '#ef4444',
  prerequisite: '#f97316',
}

function RoadmapGraph({ graph }) {
  const nodes = graph?.nodes || []
  const edges = graph?.edges || []
  if (!nodes.length) {
    return <div className="chip muted">No graph data available.</div>
  }

  const centerX = 50
  const centerY = 50
  const radius = 34
  const nodeMap = new Map(
    nodes.map((node, index) => {
      const angle = (2 * Math.PI * index) / Math.max(nodes.length, 1)
      return [
        node.id,
        {
          ...node,
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
        },
      ]
    }),
  )

  return (
    <div className="roadmap-graph-wrap">
      <svg className="roadmap-graph" viewBox="0 0 100 100" role="img" aria-label={graph.title}>
        {edges.map((edge, index) => {
          const source = nodeMap.get(edge.source)
          const target = nodeMap.get(edge.target)
          if (!source || !target) return null
          return (
            <line
              key={`edge-${index}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke="rgba(206, 210, 255, 0.42)"
              strokeWidth="0.7"
            />
          )
        })}
        {Array.from(nodeMap.values()).map((node) => (
          <g key={node.id}>
            <circle
              cx={node.x}
              cy={node.y}
              r="2.9"
              fill={STATUS_COLORS[node.status] || '#94a3b8'}
              stroke="#0f1025"
              strokeWidth="0.3"
            />
            <text x={node.x} y={node.y - 4.2} textAnchor="middle" className="graph-node-label">
              {node.label}
            </text>
          </g>
        ))}
      </svg>
      <div className="roadmap-meta-row">
        <span className="chip">Nodes: {graph.meta?.node_count ?? nodes.length}</span>
        <span className="chip">Edges: {graph.meta?.edge_count ?? edges.length}</span>
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

      <div className="panel">
        <h3>JD Roadmap Graph</h3>
        <RoadmapGraph graph={insights.roadmapGraph} />
      </div>
    </section>
  )
}

export default ResultsDashboard
