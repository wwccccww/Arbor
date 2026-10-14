/**
 * Smoke load: GET /v1/me (auth + optional Postgres RLS path).
 *
 * Prereqs:
 *   - API running (see scripts/load/serve-for-load.sh)
 *   - k6 installed: https://grafana.com/docs/k6/latest/set-up/install-k6/
 *
 * Run:
 *   k6 run scripts/load/k6-me.js
 *   BASE_URL=http://127.0.0.1:8000 k6 run --vus 30 --duration 30s scripts/load/k6-me.js
 */
import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const TENANT = __ENV.TENANT_ID || "0a000000-0000-4000-a000-000000000001";
const TOKENS = (__ENV.DEMO_TOKENS || "token-a,token-member,token-b").split(",");

export const options = {
  vus: Number(__ENV.VUS || 30),
  duration: __ENV.DURATION || "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
  },
};

export default function () {
  const token = TOKENS[(__VU + __ITER) % TOKENS.length].trim();
  const res = http.get(`${BASE_URL}/v1/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Tenant-Id": TENANT,
    },
    tags: { name: "GET /v1/me" },
  });
  check(res, {
    "status is 200": (r) => r.status === 200,
    "no 5xx": (r) => r.status < 500,
  });
  sleep(0.05);
}
