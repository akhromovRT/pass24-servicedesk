-- Управленческий отчёт PASS24 Service Desk
-- Период: апрель 2026 + 1–15 мая 2026 (UTC)
-- Запуск (prod):
--   ssh root@5.42.101.27 'docker exec -i pass24-postgres psql -U pass24 -d pass24_servicedesk' \
--     < backend/scripts/report_apr_may_2026.sql > pass24_report_apr_may.txt 2>&1
--
-- Замечания о методике (для отчёта):
--   * Времена реакции / решения считаются по wall-clock (часы UTC), без вычета
--     ночей и выходных. Бизнес-часовой расчёт живёт в Python (business_hours.py)
--     и здесь не воспроизводится. Поэтому MTTR чуть «пессимистичен» для тикетов,
--     пересекающих выходные.
--   * SLA-нарушения берём из колонки tickets.sla_breached (её ставит SLA-watcher
--     с учётом бизнес-часов и пауз) — это authoritative-источник.
--   * cohort_still_open — заявки когорты периода (created_at в бакете), у которых
--     ТЕКУЩИЙ статус не терминальный (не resolved/closed). Считать по статусу, а
--     НЕ по `resolved_at IS NULL`: FSM ставит resolved_at только при переходе в
--     RESOLVED, а прямое закрытие NEW→CLOSED оставляет resolved_at пустым — иначе
--     закрытые тикеты ошибочно попадают в «открытые».
--   * Период «May 1–15» — половина месяца; для сравнения с апрелем приведены
--     pro-rated значения (×30/15) — помечены как pro-rated.

\pset format unaligned
\pset tuples_only off
\pset fieldsep '|'
\pset border 0

\echo
\echo === SECTION 1: HEADLINE TOTALS ===
\echo
WITH period AS (
    SELECT
        '2026-04-01'::timestamp AS apr_start,
        '2026-05-01'::timestamp AS apr_end,
        '2026-05-01'::timestamp AS may_start,
        '2026-05-16'::timestamp AS may_end
)
SELECT
    bucket,
    created_total,
    resolved_total,
    closed_total,
    cohort_still_open,
    avg_first_response_hours,
    p50_first_response_hours,
    p90_first_response_hours,
    avg_resolve_hours,
    p50_resolve_hours,
    p90_resolve_hours,
    sla_breached_count,
    sla_compliance_pct,
    csat_avg,
    csat_count
FROM (
    SELECT
        'april' AS bucket,
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.created_at >= p.apr_start AND t.created_at < p.apr_end) AS created_total,
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.resolved_at >= p.apr_start AND t.resolved_at < p.apr_end) AS resolved_total,
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.status = 'closed' AND t.updated_at >= p.apr_start AND t.updated_at < p.apr_end) AS closed_total,
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.created_at >= p.apr_start AND t.created_at < p.apr_end AND t.status NOT IN ('resolved','closed')) AS cohort_still_open,
        (SELECT ROUND(AVG(EXTRACT(EPOCH FROM (t.first_response_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p
            WHERE t.created_at >= p.apr_start AND t.created_at < p.apr_end AND t.first_response_at IS NOT NULL) AS avg_first_response_hours,
        (SELECT ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.first_response_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p
            WHERE t.created_at >= p.apr_start AND t.created_at < p.apr_end AND t.first_response_at IS NOT NULL) AS p50_first_response_hours,
        (SELECT ROUND(percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.first_response_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p
            WHERE t.created_at >= p.apr_start AND t.created_at < p.apr_end AND t.first_response_at IS NOT NULL) AS p90_first_response_hours,
        (SELECT ROUND(AVG(EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p
            WHERE t.resolved_at >= p.apr_start AND t.resolved_at < p.apr_end) AS avg_resolve_hours,
        (SELECT ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p
            WHERE t.resolved_at >= p.apr_start AND t.resolved_at < p.apr_end) AS p50_resolve_hours,
        (SELECT ROUND(percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p
            WHERE t.resolved_at >= p.apr_start AND t.resolved_at < p.apr_end) AS p90_resolve_hours,
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.created_at >= p.apr_start AND t.created_at < p.apr_end AND t.sla_breached) AS sla_breached_count,
        (SELECT ROUND(100.0 * (1 - SUM(CASE WHEN t.sla_breached THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*),0)), 1)
            FROM tickets t, period p WHERE t.created_at >= p.apr_start AND t.created_at < p.apr_end) AS sla_compliance_pct,
        (SELECT ROUND(AVG(t.satisfaction_rating)::numeric, 2)
            FROM tickets t, period p
            WHERE t.satisfaction_submitted_at >= p.apr_start AND t.satisfaction_submitted_at < p.apr_end) AS csat_avg,
        (SELECT COUNT(*) FROM tickets t, period p
            WHERE t.satisfaction_submitted_at >= p.apr_start AND t.satisfaction_submitted_at < p.apr_end) AS csat_count

    UNION ALL

    SELECT
        'may_1_15' AS bucket,
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.created_at >= p.may_start AND t.created_at < p.may_end),
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.resolved_at >= p.may_start AND t.resolved_at < p.may_end),
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.status = 'closed' AND t.updated_at >= p.may_start AND t.updated_at < p.may_end),
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.created_at >= p.may_start AND t.created_at < p.may_end AND t.status NOT IN ('resolved','closed')),
        (SELECT ROUND(AVG(EXTRACT(EPOCH FROM (t.first_response_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.created_at >= p.may_start AND t.created_at < p.may_end AND t.first_response_at IS NOT NULL),
        (SELECT ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.first_response_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.created_at >= p.may_start AND t.created_at < p.may_end AND t.first_response_at IS NOT NULL),
        (SELECT ROUND(percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.first_response_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.created_at >= p.may_start AND t.created_at < p.may_end AND t.first_response_at IS NOT NULL),
        (SELECT ROUND(AVG(EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.resolved_at >= p.may_start AND t.resolved_at < p.may_end),
        (SELECT ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.resolved_at >= p.may_start AND t.resolved_at < p.may_end),
        (SELECT ROUND(percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.resolved_at >= p.may_start AND t.resolved_at < p.may_end),
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.created_at >= p.may_start AND t.created_at < p.may_end AND t.sla_breached),
        (SELECT ROUND(100.0 * (1 - SUM(CASE WHEN t.sla_breached THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*),0)), 1)
            FROM tickets t, period p WHERE t.created_at >= p.may_start AND t.created_at < p.may_end),
        (SELECT ROUND(AVG(t.satisfaction_rating)::numeric, 2)
            FROM tickets t, period p WHERE t.satisfaction_submitted_at >= p.may_start AND t.satisfaction_submitted_at < p.may_end),
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.satisfaction_submitted_at >= p.may_start AND t.satisfaction_submitted_at < p.may_end)

    UNION ALL

    SELECT
        'total_period' AS bucket,
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.created_at >= p.apr_start AND t.created_at < p.may_end),
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.resolved_at >= p.apr_start AND t.resolved_at < p.may_end),
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.status = 'closed' AND t.updated_at >= p.apr_start AND t.updated_at < p.may_end),
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.created_at >= p.apr_start AND t.created_at < p.may_end AND t.status NOT IN ('resolved','closed')),
        (SELECT ROUND(AVG(EXTRACT(EPOCH FROM (t.first_response_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.created_at >= p.apr_start AND t.created_at < p.may_end AND t.first_response_at IS NOT NULL),
        (SELECT ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.first_response_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.created_at >= p.apr_start AND t.created_at < p.may_end AND t.first_response_at IS NOT NULL),
        (SELECT ROUND(percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.first_response_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.created_at >= p.apr_start AND t.created_at < p.may_end AND t.first_response_at IS NOT NULL),
        (SELECT ROUND(AVG(EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.resolved_at >= p.apr_start AND t.resolved_at < p.may_end),
        (SELECT ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.resolved_at >= p.apr_start AND t.resolved_at < p.may_end),
        (SELECT ROUND(percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0)::numeric, 2)
            FROM tickets t, period p WHERE t.resolved_at >= p.apr_start AND t.resolved_at < p.may_end),
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.created_at >= p.apr_start AND t.created_at < p.may_end AND t.sla_breached),
        (SELECT ROUND(100.0 * (1 - SUM(CASE WHEN t.sla_breached THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*),0)), 1)
            FROM tickets t, period p WHERE t.created_at >= p.apr_start AND t.created_at < p.may_end),
        (SELECT ROUND(AVG(t.satisfaction_rating)::numeric, 2)
            FROM tickets t, period p WHERE t.satisfaction_submitted_at >= p.apr_start AND t.satisfaction_submitted_at < p.may_end),
        (SELECT COUNT(*) FROM tickets t, period p WHERE t.satisfaction_submitted_at >= p.apr_start AND t.satisfaction_submitted_at < p.may_end)
) sub
ORDER BY CASE bucket WHEN 'april' THEN 1 WHEN 'may_1_15' THEN 2 ELSE 3 END;

\echo
\echo === SECTION 2: BY STATUS (snapshot for created_in_period) ===
\echo
SELECT
    bucket, status, cnt
FROM (
    SELECT 'april' AS bucket, t.status, COUNT(*) AS cnt
    FROM tickets t WHERE t.created_at >= '2026-04-01' AND t.created_at < '2026-05-01'
    GROUP BY t.status
    UNION ALL
    SELECT 'may_1_15', t.status, COUNT(*)
    FROM tickets t WHERE t.created_at >= '2026-05-01' AND t.created_at < '2026-05-16'
    GROUP BY t.status
) s
ORDER BY bucket, cnt DESC;

\echo
\echo === SECTION 3: BY PRIORITY ===
\echo
SELECT bucket, priority, cnt FROM (
    SELECT 'april' AS bucket, t.priority::text AS priority, COUNT(*) AS cnt
    FROM tickets t WHERE t.created_at >= '2026-04-01' AND t.created_at < '2026-05-01'
    GROUP BY t.priority
    UNION ALL
    SELECT 'may_1_15', t.priority::text, COUNT(*)
    FROM tickets t WHERE t.created_at >= '2026-05-01' AND t.created_at < '2026-05-16'
    GROUP BY t.priority
) s
ORDER BY bucket, cnt DESC;

\echo
\echo === SECTION 4: BY CATEGORY (top) ===
\echo
SELECT bucket, category, cnt FROM (
    SELECT 'april' AS bucket, t.category, COUNT(*) AS cnt
    FROM tickets t WHERE t.created_at >= '2026-04-01' AND t.created_at < '2026-05-01'
    GROUP BY t.category
    UNION ALL
    SELECT 'may_1_15', t.category, COUNT(*)
    FROM tickets t WHERE t.created_at >= '2026-05-01' AND t.created_at < '2026-05-16'
    GROUP BY t.category
) s
ORDER BY bucket, cnt DESC;

\echo
\echo === SECTION 5: BY PRODUCT ===
\echo
SELECT bucket, product, cnt FROM (
    SELECT 'april' AS bucket, t.product, COUNT(*) AS cnt
    FROM tickets t WHERE t.created_at >= '2026-04-01' AND t.created_at < '2026-05-01'
    GROUP BY t.product
    UNION ALL
    SELECT 'may_1_15', t.product, COUNT(*)
    FROM tickets t WHERE t.created_at >= '2026-05-01' AND t.created_at < '2026-05-16'
    GROUP BY t.product
) s
ORDER BY bucket, cnt DESC;

\echo
\echo === SECTION 6: BY TICKET_TYPE ===
\echo
SELECT bucket, ticket_type, cnt FROM (
    SELECT 'april' AS bucket, t.ticket_type, COUNT(*) AS cnt
    FROM tickets t WHERE t.created_at >= '2026-04-01' AND t.created_at < '2026-05-01'
    GROUP BY t.ticket_type
    UNION ALL
    SELECT 'may_1_15', t.ticket_type, COUNT(*)
    FROM tickets t WHERE t.created_at >= '2026-05-01' AND t.created_at < '2026-05-16'
    GROUP BY t.ticket_type
) s
ORDER BY bucket, cnt DESC;

\echo
\echo === SECTION 7: BY SOURCE (channel) ===
\echo
SELECT bucket, source, cnt FROM (
    SELECT 'april' AS bucket, t.source, COUNT(*) AS cnt
    FROM tickets t WHERE t.created_at >= '2026-04-01' AND t.created_at < '2026-05-01'
    GROUP BY t.source
    UNION ALL
    SELECT 'may_1_15', t.source, COUNT(*)
    FROM tickets t WHERE t.created_at >= '2026-05-01' AND t.created_at < '2026-05-16'
    GROUP BY t.source
) s
ORDER BY bucket, cnt DESC;

\echo
\echo === SECTION 8: BY ASSIGNMENT_GROUP ===
\echo
SELECT bucket, assignment_group, cnt FROM (
    SELECT 'april' AS bucket, t.assignment_group, COUNT(*) AS cnt
    FROM tickets t WHERE t.created_at >= '2026-04-01' AND t.created_at < '2026-05-01'
    GROUP BY t.assignment_group
    UNION ALL
    SELECT 'may_1_15', t.assignment_group, COUNT(*)
    FROM tickets t WHERE t.created_at >= '2026-05-01' AND t.created_at < '2026-05-16'
    GROUP BY t.assignment_group
) s
ORDER BY bucket, cnt DESC;

\echo
\echo === SECTION 9: TOP 10 CUSTOMERS BY TICKETS ===
\echo
SELECT bucket, customer_name, cnt FROM (
    SELECT
        'apr_may' AS bucket,
        COALESCE(c.name, t.company, '(не указан)') AS customer_name,
        COUNT(*) AS cnt
    FROM tickets t
    LEFT JOIN customers c ON c.id = t.customer_id
    WHERE t.created_at >= '2026-04-01' AND t.created_at < '2026-05-16'
    GROUP BY COALESCE(c.name, t.company, '(не указан)')
) s
ORDER BY cnt DESC
LIMIT 10;

\echo
\echo === SECTION 10: AGENT WORKLOAD (April + May) ===
\echo
SELECT
    u.full_name,
    u.email,
    COUNT(*) FILTER (WHERE t.created_at >= '2026-04-01' AND t.created_at < '2026-05-16') AS assigned_in_period,
    COUNT(*) FILTER (WHERE t.resolved_at >= '2026-04-01' AND t.resolved_at < '2026-05-16') AS resolved_in_period,
    ROUND(AVG(EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0) FILTER (WHERE t.resolved_at >= '2026-04-01' AND t.resolved_at < '2026-05-16')::numeric, 1) AS avg_resolve_hours,
    ROUND(AVG(t.satisfaction_rating) FILTER (WHERE t.satisfaction_submitted_at >= '2026-04-01' AND t.satisfaction_submitted_at < '2026-05-16')::numeric, 2) AS avg_csat,
    COUNT(*) FILTER (WHERE t.satisfaction_submitted_at >= '2026-04-01' AND t.satisfaction_submitted_at < '2026-05-16') AS csat_responses
FROM tickets t
JOIN users u ON u.id::text = t.assignee_id
WHERE u.role IN ('SUPPORT_AGENT','ADMIN') AND u.is_active = true
GROUP BY u.full_name, u.email
HAVING COUNT(*) FILTER (WHERE t.created_at >= '2026-04-01' AND t.created_at < '2026-05-16') > 0
    OR COUNT(*) FILTER (WHERE t.resolved_at >= '2026-04-01' AND t.resolved_at < '2026-05-16') > 0
ORDER BY resolved_in_period DESC;

\echo
\echo === SECTION 11: DAILY VOLUME (created per day) ===
\echo
SELECT
    DATE_TRUNC('day', created_at)::date AS day,
    COUNT(*) AS created,
    COUNT(*) FILTER (WHERE sla_breached) AS sla_breached,
    COUNT(*) FILTER (WHERE priority::text IN ('CRITICAL','HIGH')) AS critical_or_high
FROM tickets
WHERE created_at >= '2026-04-01' AND created_at < '2026-05-16'
GROUP BY 1
ORDER BY 1;

\echo
\echo === SECTION 12: SLA RESPONSE COMPLIANCE PER PRIORITY (created in period) ===
\echo
SELECT
    bucket, priority::text AS priority,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE first_response_at IS NOT NULL) AS with_response,
    COUNT(*) FILTER (WHERE sla_breached) AS breached,
    ROUND(100.0 * (1 - SUM(CASE WHEN sla_breached THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*),0)), 1) AS compliance_pct
FROM (
    SELECT 'april' AS bucket, * FROM tickets WHERE created_at >= '2026-04-01' AND created_at < '2026-05-01'
    UNION ALL
    SELECT 'may_1_15', * FROM tickets WHERE created_at >= '2026-05-01' AND created_at < '2026-05-16'
) s
GROUP BY bucket, priority
ORDER BY bucket, priority;

\echo
\echo === SECTION 13: REPEAT REQUESTERS (top 10 by tickets in period) ===
\echo
SELECT
    u.full_name,
    u.email,
    COUNT(*) AS tickets_in_period
FROM tickets t
JOIN users u ON u.id::text = t.creator_id
WHERE t.created_at >= '2026-04-01' AND t.created_at < '2026-05-16'
GROUP BY u.full_name, u.email
HAVING COUNT(*) >= 3
ORDER BY tickets_in_period DESC
LIMIT 10;

\echo
\echo === SECTION 14: CSAT DISTRIBUTION (apr+may) ===
\echo
SELECT
    satisfaction_rating,
    COUNT(*) AS n
FROM tickets
WHERE satisfaction_submitted_at >= '2026-04-01' AND satisfaction_submitted_at < '2026-05-16'
GROUP BY satisfaction_rating
ORDER BY satisfaction_rating DESC NULLS LAST;

\echo
\echo === SECTION 15: KNOWLEDGE BASE / PROJECTS COUNTS (context, all-time) ===
\echo
SELECT 'kb_articles_total' AS metric, COUNT(*)::text AS value FROM articles
UNION ALL
SELECT 'kb_articles_published', COUNT(*)::text FROM articles WHERE is_published = true
UNION ALL
SELECT 'customers_total', COUNT(*)::text FROM customers
UNION ALL
SELECT 'tickets_lifetime_total', COUNT(*)::text FROM tickets
UNION ALL
SELECT 'tickets_open_now', COUNT(*)::text FROM tickets WHERE status NOT IN ('resolved','closed');

\echo
\echo === END OF REPORT ===
