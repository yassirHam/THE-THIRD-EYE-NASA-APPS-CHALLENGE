/** Credits and Use of Super Intelligence (SI), shown on the landing page and in the Research Lab.
 *  One list, so every place says the same thing. Keep it in step with the submission form's
 *  "Use of Super Intelligence (SI)" section, the references and the closing slide.
 *
 *  Rules (Space Apps 2026 SI guidelines):
 *  - every SI-generated image or video carries a visible label on or directly under it, naming the tool;
 *  - SI tools are never used to create, modify or include NASA logos, flags or mission identifiers.
 *  The site currently shows no SI-generated image or video (frontend/source-textures/si-generated/). */

export const SI_USE: { what: string; how: string }[] = [
  { what: 'Code', how: 'Written with SI coding assistants (Kiro, Codex and Antigravity) and reviewed by the team.' },
  { what: 'Narration voice', how: 'The story introduction voice is synthesized locally with the Kokoro-82M text-to-speech model, and labelled "Synthetic voice" where it plays.' },
  { what: 'Images and video', how: 'No SI-generated image or video appears on this site. Any that is added carries a visible label naming the tool.' },
]

export const NASA_BRANDING_RULE = 'No SI tool was used to create, modify or include NASA logos, flags or official mission identifiers.'

export const DATA_CREDITS = 'Earth maps derived from NASA Blue Marble and Black Marble imagery. Field image: VIIRS true colour, NASA GIBS. Fire glints, satellites and rings are illustrations, not NASA detections.'
