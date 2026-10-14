/**
 * Chat path with real DeepSeek + embedding API (use serve-for-load-real.sh).
 * Low VU only — supplier RPM and ~10s+ latency dominate; do not treat rps as capacity.
 *
 *   VUS=2 DURATION=20s k6 run scripts/load/k6-chat-real.js
 */
import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const TENANT = __ENV.TENANT_ID || "0a000000-0000-4000-a000-000000000001";
const THREAD_ID = __ENV.THREAD_ID || "0a000000-0000-4000-a000-000000000030";
const TOKENS = (__ENV.DEMO_TOKENS || "token-a").split(",");
const QUERIES = [
  "我们在哪家店吵的？",
  "7天无理由退货怎么规定？",
  "林夏住哪里？",
];

export const options = {
  vus: Number(__ENV.VUS || 2),
  duration: __ENV.DURATION || "20s",
  thresholds: {
    http_req_failed: ["rate<0.35"],
    http_req_duration: ["p(95)<120000"],
  },
};

export default function () {
  const token = TOKENS[(__VU + __ITER) % TOKENS.length].trim();
  const text = QUERIES[(__VU + __ITER) % QUERIES.length];
  const res = http.post(
    `${BASE_URL}/v1/threads/${THREAD_ID}/messages`,
    JSON.stringify({ text }),
    {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Tenant-Id": TENANT,
        "Content-Type": "application/json",
      },
      timeout: "120s",
      tags: { name: "POST /v1/threads/.../messages (real LLM)" },
    },
  );
  check(res, {
    "status is 200": (r) => r.status === 200,
    "not rate limited": (r) => r.status !== 429,
  });
  sleep(1);
}
