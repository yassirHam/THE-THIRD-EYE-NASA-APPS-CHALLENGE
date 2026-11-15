import type { CounterexampleView } from './model'

/** Numbers appear as the artifact gives them. Percentages are shown to two decimals for
 * reading; a real 0 stays 0 and an absent value is "Unavailable", never 0. */
const value = (n: number | undefined) => (n === undefined ? 'Unavailable' : n.toLocaleString(undefined, { maximumSignificantDigits: 6 }))
const percent = (n: number | undefined) => (n === undefined ? 'Unavailable' : `${n > 0 ? '+' : ''}${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`)

const KIND_TEXT: Record<CounterexampleView['kind'], string> = {
  illustration: 'Hand-computed illustration, not observed data',
  synthetic: 'Synthetic test example, not observed data',
}

function Item({ item }: { item: CounterexampleView }) {
  const rows = [
    item.observed && { name: 'Pooled regional rate', first: item.observed.first, second: item.observed.second, change: item.observed.changePercent },
    item.standardized && { name: `Fixed-weight rate${item.standardized.weights ? ` (weights ${item.standardized.weights})` : ''}`, first: item.standardized.first, second: item.standardized.second, change: item.standardized.changePercent },
  ].filter((row): row is { name: string; first: number; second: number; change: number | undefined } => !!row)
  return (
    <article className="lab__counterexample" aria-labelledby={`cx-${item.id}`}>
      <p className="lab__counterexample-kind">{KIND_TEXT[item.kind]}</p>
      <h4 id={`cx-${item.id}`}>{item.label}</h4>
      {item.text && <p>{item.text}</p>}
      {rows.length > 0 && (
        <div className="lab__table-wrap">
          <table className="lab__table">
            <caption>Same block rates, different area mix</caption>
            <thead><tr><th scope="col">Measure</th><th scope="col">Period 1</th><th scope="col">Period 2</th><th scope="col">Change</th></tr></thead>
            <tbody>{rows.map((row) => <tr key={row.name}><th scope="row">{row.name}</th><td>{value(row.first)}</td><td>{value(row.second)}</td><td>{percent(row.change)}</td></tr>)}</tbody>
          </table>
        </div>
      )}
      {item.blockRates && <p className="lab__note">Block rates in both periods: {item.blockRates.map((b) => `${b.id} ${value(b.rate)}`).join(', ')}.</p>}
      {item.note && <p className="lab__note">{item.note}</p>}
      {item.limits.length > 0 && <ul className="lab__limits">{item.limits.map((limit) => <li key={limit}>{limit}</li>)}</ul>}
    </article>
  )
}

export default function Counterexamples({ items }: { items: CounterexampleView[] }) {
  if (!items.length) return null
  return <div className="lab__counterexamples">{items.map((item) => <Item key={item.id} item={item} />)}</div>
}
