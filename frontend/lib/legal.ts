// lib/legal.ts
//
// The facts the legal documents depend on, in one place. The bracketed
// values MUST be completed by counsel before launch: they are the legal
// entity, its address and the governing jurisdiction, and no one should
// guess at them. See docs/DEPLOYMENT.md, "Before you make it public".

export const LEGAL = {
  serviceName: "Aureus Intelligence",
  entityName: "[Legal entity name]",
  entityAddress: "[Registered business address]",
  governingLaw: "[State or country of governing law]",
  arbitrationSeat: "[City and state of arbitration]",
  lastUpdated: "September 15, 2026",
  contact: {
    legal: "legal@aureusintelligence.com",
    privacy: "privacy@aureusintelligence.com",
    support: "support@aureusintelligence.com",
  },
} as const;
