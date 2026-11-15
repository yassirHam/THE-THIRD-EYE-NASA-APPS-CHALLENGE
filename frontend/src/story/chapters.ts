import type { FieldView, SeamView } from '../lib/field'

export type Art =
  | { kind: 'third' }
  | {
      kind: 'field'
      view: FieldView
      clouds?: boolean
      /** parallel universe: chunks under cloud are counted as seen with no fire */
      cloudsAsZero?: boolean
      toggles?: boolean
    }
  | { kind: 'seam'; view: SeamView; headline?: string }
  | { kind: 'verdict' }

export interface Choice {
  label: string
  /** Node id in this chapter, a chapter id prefixed with '#', or a route starting with '/'. */
  to: string
  /** marks the answer that keeps the reader in the main universe */
  correct?: boolean
  /** returns from a parallel universe to the question node named in `to` */
  back?: boolean
}

export interface StoryNode {
  id: string
  text: string[]
  /** When set, the node asks the reader something and the choices are their possible answers. */
  question?: string
  /** 'parallel' nodes show where a wrong answer leads, then send the reader back */
  universe?: 'parallel'
  /** where "Skip step" goes; defaults to the correct answer, then the first choice */
  skip?: string
  art?: Art
  choices: Choice[]
}

export interface Chapter {
  id: string
  title: string
  hint: string
  caption: string
  art: Art
  nodes: StoryNode[]
}

/** Where "Skip step" leads from a node: never into a parallel universe. */
export function skipTarget(node: StoryNode) {
  return node.skip ?? (node.choices.find((c) => c.correct) ?? node.choices[0]).to
}

/** Story Mode script. Every illustration in this mode is constructed or labelled; chapters say so
 *  on screen. Wording follows THE_THIRD_EYE_FRONTEND_CONTRACT.md: the third eye reviews comparisons,
 *  it does not see hidden fire or a third sensor. */
export const CHAPTERS: Chapter[] = [
  {
    id: 'third-eye',
    title: 'Open the third eye',
    hint: 'Find out what it looks for.',
    caption: 'Reviews both records. Sees no extra fire.',
    art: { kind: 'third' },
    nodes: [
      {
        id: 'start',
        text: [
          "Hello, I'm Professor Orez. Two satellites can observe the same Earth and tell different stories. Let's investigate why.",
          'We divide the observation area into small chunks. In the scientific data, these are grid cells.',
          'Two satellite eyes wrote that history. They never saw the ground the same way.',
          'The third eye does not see more fire. It checks whether a comparison between the two records holds up, and tells you when it does not.',
        ],
        choices: [
          { label: 'Show me the two eyes.', to: '#two-eyes' },
          { label: 'What does the third eye check?', to: 'checks' },
        ],
      },
      {
        id: 'checks',
        text: [
          'Three things. Whether the change of satellite could flip the answer. Whether there were enough clear days to count. Whether the correction was ever tested where you are looking.',
          'If any of those is missing, you get the reason instead of a confident chart.',
        ],
        choices: [{ label: 'Show me the two eyes.', to: '#two-eyes' }],
      },
    ],
  },
  {
    id: 'two-eyes',
    title: 'Compare the two eyes',
    hint: 'Look through MODIS, then VIIRS.',
    caption: 'Same land, same day, different chunks.',
    art: { kind: 'field', view: 'ground', toggles: true },
    nodes: [
      {
        id: 'start',
        art: { kind: 'field', view: 'ground', toggles: true },
        text: ['This is a real piece of eastern Angola, seen from orbit in June, the start of the fire season. Each glowing dot is a fire we placed there to teach with.'],
        choices: [{ label: 'Look through MODIS.', to: 'modis' }],
      },
      {
        id: 'modis',
        art: { kind: 'field', view: 'modis', toggles: true },
        text: [
          'MODIS, on the Aqua satellite since 2002, marks a chunk when it detects fire anywhere inside it.',
          'Its chunks are large. A small fire inside one can be too faint, against the rest of the chunk, to be detected.',
        ],
        choices: [{ label: 'Look through VIIRS.', to: 'viirs' }],
      },
      {
        id: 'viirs',
        art: { kind: 'field', view: 'viirs', toggles: true },
        text: [
          'VIIRS, on Suomi NPP from 2012, looks through smaller chunks and often detects smaller fires. Its sensor and detection method differ too, not only the chunk size.',
          'Same land, same day, more chunks lit.',
        ],
        question: 'So which eye is right?',
        skip: 'both',
        choices: [
          { label: 'The coarse eye, MODIS.', to: 'u-modis' },
          { label: 'The fine eye, VIIRS.', to: 'u-viirs' },
          { label: 'Neither, on its own.', to: 'both', correct: true },
        ],
      },
      {
        id: 'u-modis',
        universe: 'parallel',
        art: { kind: 'field', view: 'modis' },
        text: [
          'In this universe, only the coarse eye is trusted.',
          'Fires too small or too faint for its big chunks never enter the record. Every season looks calmer than the ground was, and nobody can say by how much.',
        ],
        skip: 'both',
        choices: [{ label: 'Go back and answer again.', to: 'viirs', back: true }],
      },
      {
        id: 'u-viirs',
        universe: 'parallel',
        art: { kind: 'seam', view: 'stitched' },
        text: [
          'In this universe, only the fine eye is trusted.',
          'But it opened in 2012. Every year before that was seen by the coarse eye. Read the two as one record and fire seems to almost double the year the fine eye arrives.',
        ],
        skip: 'both',
        choices: [{ label: 'Go back and answer again.', to: 'viirs', back: true }],
      },
      {
        id: 'both',
        art: { kind: 'field', view: 'both', toggles: true },
        text: [
          'Neither is right on its own, and neither is wrong. They count chunks where fire was detected, not fires, and each eye detects differently.',
          'The fine eye lights more chunks. The coarse eye marks a larger share of its own, bigger chunks. Neither number is the amount of fire, which is why the two records cannot simply be joined end to end.',
        ],
        choices: [{ label: 'What about cloudy days?', to: '#clouds' }],
      },
    ],
  },
  {
    id: 'clouds',
    title: 'Count only what was seen',
    hint: 'A chunk nobody saw is not a chunk without fire.',
    caption: 'Hazy chunks were never seen.',
    art: { kind: 'field', view: 'modis', clouds: true },
    nodes: [
      {
        id: 'start',
        text: ['Clouds roll in. Under them, neither eye can see fire, or the absence of it.'],
        question: 'How should the cloudy chunks count?',
        skip: 'right',
        choices: [
          { label: 'Count the cloudy chunks as no fire.', to: 'u-zero' },
          { label: 'Leave the cloudy chunks out.', to: 'right', correct: true },
        ],
      },
      {
        id: 'u-zero',
        universe: 'parallel',
        art: { kind: 'field', view: 'modis', clouds: true, cloudsAsZero: true },
        text: [
          'In this universe, every cloudy chunk counts as a chunk with no fire.',
          'Look at the rate: it drops, because chunks nobody could see now count as calm. Every cloudy month and every rainy season looks quieter than it was.',
        ],
        skip: 'right',
        choices: [{ label: 'Go back and answer again.', to: 'start', back: true }],
      },
      {
        id: 'right',
        text: ['Right. Leave chunks classified as unobserved or unusable under the product policy out of the usable-observation count.'],
        choices: [{ label: 'And what does the calendar show?', to: 'rate' }],
      },
      {
        id: 'rate',
        text: [
          'The calendar reports detected fire-cell-days per 1,000 usable land-cell-days.',
          'When a month has no clear chunks at all, it reads unavailable, never zero.',
        ],
        choices: [{ label: 'Show me where the eyes change.', to: '#seam' }],
      },
    ],
  },
  {
    id: 'seam',
    title: 'Find the seam',
    hint: 'Where one eye hands over to the other.',
    caption: 'Made-up record, real problem.',
    art: { kind: 'seam', view: 'stitched' },
    nodes: [
      {
        id: 'start',
        art: { kind: 'seam', view: 'stitched' },
        text: ['Join the two records into one line and this happens. Fire seems to almost double in 2012.'],
        question: 'Did fire really double in 2012?',
        skip: 'eyes',
        choices: [
          { label: 'Yes, the line says so.', to: 'u-double' },
          { label: 'Not sure. The eye changed that year.', to: 'eyes', correct: true },
        ],
      },
      {
        id: 'u-double',
        universe: 'parallel',
        art: { kind: 'seam', view: 'stitched', headline: 'Fire doubles across the region' },
        text: [
          'In this universe, the jump is read as real.',
          'Reports say fire doubled in 2012. Plans and budgets follow, and every later year is measured against a step that came from changing eyes, not from the ground.',
        ],
        skip: 'eyes',
        choices: [{ label: 'Go back and answer again.', to: 'start', back: true }],
      },
      {
        id: 'eyes',
        art: { kind: 'seam', view: 'both-eyes' },
        text: [
          'Draw each eye separately. The first eye kept watching after 2012 and saw no jump.',
          'Most of that step comes from switching eyes, not from the ground.',
        ],
        choices: [{ label: 'Can it be fixed?', to: 'fix' }],
      },
      {
        id: 'fix',
        art: { kind: 'seam', view: 'corrected' },
        text: [
          'One fix is to rescale the second eye to the first, using years when both were watching.',
          'In this made-up record the step mostly disappears. Real records are less tidy.',
        ],
        choices: [{ label: 'How do you know the fix works?', to: 'test' }],
      },
      {
        id: 'test',
        art: { kind: 'seam', view: 'corrected' },
        text: [
          'We test it. THE THIRD EYE keeps the first eye through 2019 and switches in 2020.',
          'Before trusting that switch, it stages a fake one in years when both eyes were open, and checks whether the corrected record still points the same way as the first eye alone.',
          'If the fix fails that test, the app tells you so.',
        ],
        choices: [{ label: 'So what answer do I get?', to: '#verdict' }],
      },
    ],
  },
  {
    id: 'verdict',
    title: 'Read the verdict',
    hint: 'Five honest answers.',
    caption: 'None of them says proven.',
    art: { kind: 'verdict' },
    nodes: [
      {
        id: 'start',
        text: [
          'Ask whether one season was busier than another, and the third eye answers in one of five ways.',
          'A consistent answer means the tested corrections agree. It does not mean the satellites saw every fire.',
        ],
        choices: [
          { label: 'What happens when an eye closes for good?', to: 'closing' },
          { label: 'Open the Research Lab.', to: '/lab' },
        ],
      },
      {
        id: 'closing',
        text: [
          'It already has. Suomi NPP stopped sending new data on 2 November 2026, so its record is now closed.',
          'The next eyes, on NOAA-20 and NOAA-21, start with no inherited trust. Each one has to pass its own test before the calendar joins it.',
        ],
        choices: [
          { label: 'Open the Research Lab.', to: '/lab' },
          { label: 'Back to the start.', to: '/' },
        ],
      },
    ],
  },
]

export const VERDICTS: { label: string; meaning: string; tone: 'ok' | 'warn' | 'gap' | 'out' | 'fail' }[] = [
  { label: 'Consistent across tested corrections', meaning: 'Every tested correction gives the same answer.', tone: 'ok' },
  { label: 'Depends on the correction', meaning: 'Tested corrections disagree. You see both.', tone: 'warn' },
  { label: 'Not enough usable evidence', meaning: 'Too few clear days, or a check is missing.', tone: 'gap' },
  { label: 'Outside evaluated calibration', meaning: 'Raw data is shown; the correction was never tested here.', tone: 'out' },
  { label: 'Calibration check failed', meaning: 'The correction was tested here and failed.', tone: 'fail' },
]

export function chapterIndex(id: string) {
  return CHAPTERS.findIndex((c) => c.id === id)
}
