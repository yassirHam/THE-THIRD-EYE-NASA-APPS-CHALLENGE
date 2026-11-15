import Counterexamples from './Counterexamples'
import type { EvidenceView } from './model'

/** Geographic composition section of the Lab (plan Section 4B), fed by the bundle's Stage A
 * evidence documents. Worked illustrations are shown; real-data checks wait for release. */
export default function Composition({ evidence }: { evidence: EvidenceView[] }) {
  const items = evidence.flatMap((doc) => doc.counterexamples)
  const withheld = evidence.reduce((sum, doc) => sum + (doc.released ? 0 : doc.withheldCount), 0)
  const released = evidence.length > 0 && evidence.every((doc) => doc.released)
  return (
    <section className="lab__comparison" aria-labelledby="composition-title">
      <div className="lab__sectionhead">
        <div><p className="lab__eyebrow">Reading regional rates</p><h3 id="composition-title">Why the area mix matters</h3></div>
        <span className="lab__status">{!evidence.length ? 'Unavailable' : released ? 'Released' : 'Not released'}</span>
      </div>
      {evidence.length ? <>
        <p>A rate pooled over several areas can move when only the share of usable observations in each area changes, even if every area's own rate stays the same. Holding the area weights fixed removes that effect. This is why each area is evaluated on its own and regional rates are never averaged.</p>
        <Counterexamples items={items} />
        {withheld > 0 && <p className="lab__note">{withheld === 1 ? 'One real-data composition check' : `${withheld} real-data composition checks`} from this evidence file {withheld === 1 ? 'is' : 'are'} not shown until {withheld === 1 ? 'it is' : 'they are'} approved and independently verified.</p>}
      </> : <p>The composition example will appear when its evidence file is available.</p>}
    </section>
  )
}
