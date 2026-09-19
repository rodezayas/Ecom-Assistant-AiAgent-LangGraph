-- Enable RLS and policies for golden dataset tables
-- Run in Supabase SQL Editor after the MVP migration

-- golden_queries: public read for active rows, service_role full access
alter table if exists public.golden_queries enable row level security;

drop policy if exists "anon read active golden queries" on public.golden_queries;
create policy "anon read active golden queries"
  on public.golden_queries for select
  to anon, authenticated
  using (is_active = true);

drop policy if exists "service_role all golden queries" on public.golden_queries;
create policy "service_role all golden queries"
  on public.golden_queries for all
  to service_role
  using (true) with check (true);

-- evaluation_runs
alter table if exists public.evaluation_runs enable row level security;

drop policy if exists "anon read evaluation runs" on public.evaluation_runs;
create policy "anon read evaluation runs"
  on public.evaluation_runs for select
  to anon, authenticated
  using (true);

drop policy if exists "service_role all evaluation runs" on public.evaluation_runs;
create policy "service_role all evaluation runs"
  on public.evaluation_runs for all
  to service_role
  using (true) with check (true);

-- evaluation_results
alter table if exists public.evaluation_results enable row level security;

drop policy if exists "anon read evaluation results" on public.evaluation_results;
create policy "anon read evaluation results"
  on public.evaluation_results for select
  to anon, authenticated
  using (true);

drop policy if exists "service_role all evaluation results" on public.evaluation_results;
create policy "service_role all evaluation results"
  on public.evaluation_results for all
  to service_role
  using (true) with check (true);
