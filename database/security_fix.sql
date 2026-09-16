-- ════════════════════════════════════════════════════════════════
-- Agent Eye — Supabase Security Hardening
-- Run this in Supabase dashboard → SQL Editor → New query
--
-- Fixes:
--   1. Revokes PostgREST access to all our tables (the /rest/v1 API)
--   2. Enables Row-Level Security on all tables
--   3. Adds deny-all policies for anon and authenticated roles
--
-- Safe to run multiple times. Our FastAPI backend connects as the
-- `postgres` superuser (via the pooler URL), which BYPASSES RLS,
-- so the app continues to work normally after this runs.
-- ════════════════════════════════════════════════════════════════

-- ── 1. Revoke PostgREST (anon + authenticated) access ───────────
REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;

-- ── 2. Enable Row-Level Security ─────────────────────────────────
ALTER TABLE users         ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE detections    ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts        ENABLE ROW LEVEL SECURITY;
ALTER TABLE known_faces   ENABLE ROW LEVEL SECURITY;

-- ── 3. Force RLS even for table owners (defense in depth) ────────
ALTER TABLE users         FORCE ROW LEVEL SECURITY;
ALTER TABLE user_settings FORCE ROW LEVEL SECURITY;
ALTER TABLE agents        FORCE ROW LEVEL SECURITY;
ALTER TABLE detections    FORCE ROW LEVEL SECURITY;
ALTER TABLE alerts        FORCE ROW LEVEL SECURITY;
ALTER TABLE known_faces   FORCE ROW LEVEL SECURITY;

-- ── 4. Deny-all policies for anon and authenticated ─────────────
-- (only the postgres superuser — used by our FastAPI backend —
--  can read/write data, bypassing RLS automatically)

DO $$
DECLARE t text;
BEGIN
  FOR t IN SELECT unnest(ARRAY[
    'users', 'user_settings', 'agents', 'detections', 'alerts', 'known_faces'
  ])
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS deny_anon ON %I', t);
    EXECUTE format('DROP POLICY IF EXISTS deny_auth ON %I', t);
    EXECUTE format(
      'CREATE POLICY deny_anon ON %I FOR ALL TO anon USING (false) WITH CHECK (false)', t);
    EXECUTE format(
      'CREATE POLICY deny_auth ON %I FOR ALL TO authenticated USING (false) WITH CHECK (false)', t);
  END LOOP;
END $$;

-- ── 5. Verify the fix ────────────────────────────────────────────
SELECT
  n.nspname AS schema,
  c.relname AS table,
  c.relrowsecurity AS rls_enabled,
  c.relforcerowsecurity AS rls_forced
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN ('users','user_settings','agents','detections','alerts','known_faces')
  AND c.relkind = 'r'
ORDER BY c.relname;
