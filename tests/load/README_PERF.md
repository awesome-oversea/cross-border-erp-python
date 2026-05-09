# ERP Python Performance Test Plan

## 1. Test Objectives
- Verify system stability under concurrent load
- Identify performance bottlenecks and breaking points
- Validate response time SLAs for critical APIs
- Measure resource utilization under load

## 2. SLA Targets

| API Category | P50 | P90 | P95 | P99 | Max RPS |
|---|---|---|---|---|---|
| Health/Config | <10ms | <20ms | <30ms | <50ms | 500 |
| List/Query | <100ms | <300ms | <500ms | <1000ms | 200 |
| Create/Update | <200ms | <500ms | <800ms | <1500ms | 100 |
| Report/Export | <500ms | <1500ms | <3000ms | <5000ms | 50 |

## 3. Test Scenarios

### 3.1 Smoke Test
- 10 concurrent users, 30 seconds
- Verify all endpoints return 200

### 3.2 Average Load Test
- 50 concurrent users, 5 minutes
- Ramp-up: 10 seconds
- Target: All APIs within SLA

### 3.3 Peak Load Test
- 200 concurrent users, 10 minutes
- Ramp-up: 30 seconds
- Target: Error rate < 1%, P95 within SLA

### 3.4 Stress Test
- 500 concurrent users, 15 minutes
- Ramp-up: 60 seconds
- Target: System remains stable, graceful degradation

### 3.5 Endurance Test
- 100 concurrent users, 2 hours
- Target: No memory leaks, consistent performance

## 4. Key Metrics
- Requests per second (RPS)
- Response time percentiles (P50/P90/P95/P99)
- Error rate
- CPU/Memory utilization
- Database connection pool usage
- Redis hit rate

## 5. Critical API Paths
1. Order list + detail (OMS)
2. Inventory query (WMS)
3. Product search (PDM)
4. Financial reports (FMS)
5. Dashboard aggregation (BI)
6. AI suggestion processing (SYS/PMS)

## 6. Tools
- Primary: Locust / custom async load test (tests/load/load_test.py)
- Monitoring: Prometheus + Grafana dashboards
- APM: OpenTelemetry + Jaeger
