-- Runs (uploaded PDF + completed analysis), the job queue, per-page OCR text and the audit log.
-- The backend connects with the service role and always filters by user_id. RLS below is defence in depth
-- and is only created where Supabase's auth schema exists (plain Postgres in tests has none).
create extension if not exists pgcrypto;

create table if not exists runs (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null,
  created_at    timestamptz not null default clock_timestamp(),
  updated_at    timestamptz not null default clock_timestamp(),
  file_name     text not null,
  pdf_sha256    text not null,
  storage_key   text not null,
  page_count    integer not null check (page_count > 0),
  status        text not null default 'queued'
                check (status in ('queued', 'processing', 'resolved', 'unsupported', 'ambiguous', 'failed')),
  result        jsonb,
  error         text,
  parent_run_id uuid references runs (id),
  switches      jsonb,
  versions      jsonb
);
create index if not exists runs_user_created on runs (user_id, created_at desc, id desc);

create table if not exists jobs (
  id         bigserial primary key,
  run_id     uuid not null references runs (id) on delete cascade,
  state      text not null default 'queued' check (state in ('queued', 'running', 'done', 'failed')),
  attempts   integer not null default 0,
  locked_at  timestamptz,
  last_error text,
  created_at timestamptz not null default clock_timestamp()
);
create index if not exists jobs_claimable on jobs (state, id);

create table if not exists pages (
  run_id     uuid not null references runs (id) on delete cascade,
  page_no    integer not null,
  ocr_rapid  text,
  ocr_tess   text,
  text_layer text,
  primary key (run_id, page_no)
);

create table if not exists audit_events (
  id     bigserial primary key,
  actor  text not null,
  action text not null,
  entity text not null,
  at     timestamptz not null default clock_timestamp()
);

do $$
begin
  if exists (select 1 from pg_namespace where nspname = 'auth') then
    alter table runs enable row level security;
    alter table jobs enable row level security;
    alter table pages enable row level security;
    alter table audit_events enable row level security;
    if not exists (select 1 from pg_policies where tablename = 'runs' and policyname = 'runs_owner') then
      execute 'create policy runs_owner on runs for select using (user_id = auth.uid())';
    end if;
  end if;
end $$;
