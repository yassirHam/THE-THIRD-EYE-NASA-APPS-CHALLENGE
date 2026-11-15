/** Demo-recording switch, requested by the team for the video.
 * false: review notices (preliminary, not yet approved, not yet verified, not tested on the
 * sealed years, release status) are hidden. Every number is unchanged either way.
 * Set back to true after the recording, before submission review. */
export const SHOW_REVIEW_NOTICES = false

/** Demo-recording switch: extra region names on the map and in the area lists, for show only.
 * They carry no numbers, cannot be selected, and say "Not processed yet". Set to false (or delete
 * this list) after the recording. See frontend/DEMO_LIMITS_TODO.md. */
export const SHOW_PLACEHOLDER_REGIONS = true
export const PLACEHOLDER_REGIONS: Array<{ id: string; name: string; lon: number; lat: number }> = [
  { id: 'demo-angola', name: 'Angola (miombo savanna)', lon: 17.8, lat: -11.2 },
  { id: 'demo-amazon', name: 'Brazilian Amazon', lon: -55.0, lat: -8.5 },
  { id: 'demo-australia', name: 'Northern Australia', lon: 133.0, lat: -16.0 },
  { id: 'demo-siberia', name: 'Eastern Siberia', lon: 125.0, lat: 62.0 },
  { id: 'demo-iberia', name: 'Iberian Peninsula', lon: -5.5, lat: 40.0 },
  { id: 'demo-sahel', name: 'Sahel (West Africa)', lon: 2.0, lat: 12.5 },
  { id: 'demo-indonesia', name: 'Kalimantan, Indonesia', lon: 114.0, lat: -1.0 },
]
