import type { ReactNode } from 'react'

/* Machine translation (Chrome's "Translate this page", the Google Translate widget) rewrites the
   page's text nodes one by one. Two kinds of text break under that:

   - Proper names get translated: THE THIRD EYE became "IMAGE DIFFÉRÉE" and Suomi NPP became
     "centrale nucléaire de Suomi" in French. <Name> and <Keep> mark them translate="no".
   - Text split into letters or lines for an animation gets translated piece by piece, which
     turned THE THIRD EYE into "UNFTERjeMUNGE" and left typed lines nearly empty. <Animated> keeps a
     whole copy of the sentence for translators and screen readers, next to the animated copy.
     global.css shows the whole copy instead of the animated one once the page is translated. */

const NAMES = /(THE THIRD EYE|The Third Eye|Suomi NPP)/

/** A proper name that must not be translated. */
export function Name({ children }: { children: string }) {
  return <span translate="no" className="notranslate">{children}</span>
}

/** A sentence whose proper names stay untranslated; the rest translates normally. */
export function Keep({ text }: { text: string }) {
  if (!NAMES.test(text)) return <>{text}</>
  return <>{text.split(NAMES).map((part, i) => (i % 2 ? <Name key={i}>{part}</Name> : part))}</>
}

/** Text with an animated copy (letters or lines) that translators must not touch. */
export function Animated({ text, children }: { text: string; children?: ReactNode }) {
  return (
    <>
      <span className="tx-whole"><Keep text={text} /></span>
      <span className="tx-anim notranslate" translate="no" aria-hidden="true">{children ?? text}</span>
    </>
  )
}
