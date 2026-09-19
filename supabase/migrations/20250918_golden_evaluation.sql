-- Copiar/pegar en Supabase SQL Editor para crear tablas de evaluación
-- Requiere que public.golden_queries ya exista (MVP)
create table if not exists public.evaluation_runs (
  id uuid primary key default gen_random_uuid(),
  dataset_version text not null default 'v1',
  git_commit text,
  model_config jsonb not null default '{}',
  config_snapshot jsonb not null default '{}',
  total_queries int not null default 0,
  passed int not null default 0,
  failed int not null default 0,
  run_by text,
  run_at timestamptz not null default now()
);
create index if not exists idx_evaluation_runs_at on public.evaluation_runs(run_at desc);

create table if not exists public.evaluation_results (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.evaluation_runs(id) on delete cascade,
  golden_query_id uuid not null references public.golden_queries(id) on delete cascade,
  golden_slug text not null,
  query_text text not null,
  actual_intent text,
  actual_guardrail_blocked boolean,
  actual_guardrail_reason text,
  actual_product_ids text[] not null default '{}',
  actual_response_text text,
  passed boolean not null,
  failed_checks text[] not null default '{}',
  latency_ms int,
  retrieval_source text,
  llm_chosen_provider text,
  phoenix_trace_id text,
  phoenix_trace_url text,
  thread_id text,
  scored_at timestamptz not null default now(),
  unique(run_id, golden_query_id)
);
create index if not exists idx_evaluation_results_run on public.evaluation_results(run_id);
create index if not exists idx_evaluation_results_passed on public.evaluation_results(passed);
create index if not exists idx_evaluation_results_slug on public.evaluation_results(golden_slug);
