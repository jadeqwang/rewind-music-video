// agency.js: the time-enforcement agency hunting her (her rewinds leave detectable anomalies). User's choice: TIME VARIANCE
// with the last word always a black redaction bar. IP rule: never the word that follows, never its initials, no logo /
// hexagon / props / characters / typography from any franchise. ?agency=oci switches to the invented fallback.
const AG = {
  tv:  { header: ['TIME', 'VARIANCE', { bar: 8 }], mark: ['T.V.', { bar: 1 }], code: 'TV-D-7' },
  oci: { header: ['OFFICE OF CAUSAL INTEGRITY'], mark: ['OCI'], code: 'OCI-D-7' },
};
export const AGENCY_DEFAULT = 'tv';
export const AGENCY = AG[new URLSearchParams(typeof location !== 'undefined' ? location.search : '').get('agency')] || AG[AGENCY_DEFAULT];
