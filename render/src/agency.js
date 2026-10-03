// agency.js: the time-enforcement agency hunting her (her rewinds leave detectable anomalies). User's choice: TIME VARIANCE
// with the last word always a black redaction bar. IP rule: never the word that follows, never its initials, no logo /
// hexagon / props / characters / typography from any franchise. ?agency=oci switches to the invented fallback.
const AG = {
  tv:  { header: ['TIME', 'VARIANCE', { bar: 9 }]   /* bar = exactly 9 mono chars (the redacted word's width) */, mark: ['T.V.', { bar: 1 }], code: 'TV-D-7', classif: 'TEMPORAL // EYES ONLY' },
  oci: { header: ['OFFICE OF CAUSAL INTEGRITY'], mark: ['OCI'], code: 'OCI-D-7', classif: 'TEMPORAL // EYES ONLY' },
};
export const AGENCY_DEFAULT = 'tv';
// file numbers: TV-D-7 / BRANCH 0001 (never a real agency's file-number format, classification or exemption code)
export const fileNo = (n = 1, A = null) => `${(A || AGENCY).code} / BRANCH ${String(n).padStart(4, '0')}`;
export const AGENCY = AG[new URLSearchParams(typeof location !== 'undefined' ? location.search : '').get('agency')] || AG[AGENCY_DEFAULT];
