import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';

const ttft = new Trend('ttft_ms');
const totalTime = new Trend('total_ms');
const successRate = new Rate('success_rate');
const errorCount = new Counter('error_count');

const queries = new SharedArray('queries', function () {
  return JSON.parse(open('./benchmark_queries.json'));
});

function generateSessionId(prefix) {
  const hex = 'xxxxxxxxxxxx4xxxyxxxxxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
  return `${prefix}-${hex}`;
}

function parseSSE(body, metrics) {
  let firstDataTime = null;
  let foundDone = false;
  let dataLines = [];

  const lines = body.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('data: ')) {
      if (firstDataTime === null) {
        firstDataTime = metrics.startTime;
        metrics.ttftMs = (firstDataTime - metrics.requestStart) * 1000;
      }
      try {
        const payload = JSON.parse(trimmed.substring(6));
        if (payload.type === 'done') {
          foundDone = true;
        }
      } catch (e) {
        // skip malformed JSON
      }
    }
  }

  metrics.foundDone = foundDone;
  metrics.dataLines = dataLines;

  if (metrics.ttftMs === null) {
    metrics.ttftMs = metrics.duration;
  }
}

export const options = {
  stages: [
    { duration: '30s', target: 1 },
    { duration: '1m', target: 1 },
    { duration: '30s', target: 3 },
    { duration: '1m', target: 3 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    ttft_ms: ['p95<10000'],
    total_ms: ['p95<60000'],
    success_rate: ['rate>0.9'],
  },
  tags: {
    name: 'chat-benchmark',
  },
};

const BASE_URL = __ENV.BENCHMARK_URL || 'http://localhost:9000';
const CHAT_URL = `${BASE_URL}/api/chat`;
const SESSION_PREFIX = __ENV.SESSION_PREFIX || 'k6-bench';

export default function () {
  const query = queries[Math.floor(Math.random() * queries.length)];
  const sessionId = generateSessionId(SESSION_PREFIX);

  const payload = JSON.stringify({
    message: query.message,
    session_id: sessionId,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
    tags: {
      query_label: query.label,
      query_category: query.category,
    },
    timeout: '120s',
  };

  const requestStart = Date.now();
  const res = http.post(CHAT_URL, payload, params);
  const duration = res.timings.duration;

  const metrics = {
    duration: duration,
    requestStart: requestStart,
    startTime: Date.now(),
    ttftMs: null,
    foundDone: false,
  };

  const success = check(res, {
    'status is 200': (r) => r.status === 200,
  });

  if (success) {
    parseSSE(res.body, metrics);

    ttft.add(metrics.ttftMs);
    totalTime.add(duration);

    const hasDone = check(null, {
      'sse done event received': () => metrics.foundDone,
    });

    successRate.add(hasDone);

    if (!metrics.foundDone) {
      errorCount.add(1);
      console.warn(`Missing done event for [${query.label}] session=${sessionId}`);
    }
  } else {
    successRate.add(false);
    errorCount.add(1);
    console.error(`HTTP ${res.status} for [${query.label}] session=${sessionId}`);
  }

  sleep(6 + Math.random() * 4);
}
