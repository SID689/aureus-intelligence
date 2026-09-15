// lib/realtime-server.ts — SERVER ONLY (it reads INTERNAL_API_SECRET).
//
// Mints the short-lived tokens backend/app/core/realtime_auth.py verifies.
// The two implementations must stay byte-compatible:
//
//   token = "v1." + b64url(payload) + "." + b64url(HMAC-SHA256(key, "v1." + b64url(payload)))
//   key   = HMAC-SHA256(INTERNAL_API_SECRET, "aureus-realtime-token-v1")
//
// b64url is unpadded. The payload's key order and spacing need not match
// Python's json.dumps: the signature covers the encoded bytes as sent, and
// the verifier only parses them afterwards.
import { createHmac } from "crypto";

const AUDIENCE = "aureus-realtime";
const KEY_CONTEXT = "aureus-realtime-token-v1";
const MAX_TTL_SECONDS = 900;
export const REALTIME_TOKEN_TTL_SECONDS = 300;

function signingKey(): Buffer {
  const secret = process.env.INTERNAL_API_SECRET || "";
  if (!secret) throw new Error("INTERNAL_API_SECRET is not configured");
  return createHmac("sha256", secret).update(KEY_CONTEXT).digest();
}

export function mintRealtimeToken(
  userId: string,
  ttlSeconds = REALTIME_TOKEN_TTL_SECONDS,
): { token: string; expiresAt: number } {
  const now = Math.floor(Date.now() / 1000);
  const exp = now + Math.max(1, Math.min(ttlSeconds, MAX_TTL_SECONDS));
  const body = Buffer.from(JSON.stringify({ sub: userId, aud: AUDIENCE, iat: now, exp })).toString("base64url");
  const signingInput = `v1.${body}`;
  const sig = createHmac("sha256", signingKey()).update(signingInput).digest("base64url");
  return { token: `${signingInput}.${sig}`, expiresAt: exp };
}
