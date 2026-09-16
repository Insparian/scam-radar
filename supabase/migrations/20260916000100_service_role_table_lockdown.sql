begin;

-- Hosted Supabase may retain non-DML table privileges for service_role even when
-- automatic table exposure is disabled. Worker and exporter access is RPC-only,
-- so remove every direct table and sequence privilege now and by default.
revoke all on all tables in schema public from service_role;
revoke all on all sequences in schema public from service_role;

alter default privileges in schema public revoke all on tables from service_role;
alter default privileges in schema public revoke all on sequences from service_role;

commit;
