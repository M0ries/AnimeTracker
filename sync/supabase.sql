-- Run in the SQL editor of the owner's Supabase project.
create table if not exists public.at_snapshots (
  user_id uuid primary key references auth.users(id) on delete cascade,
  revision bigint not null default 1 check (revision > 0),
  document jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.at_snapshots enable row level security;
revoke all on public.at_snapshots from anon;
grant select, insert on public.at_snapshots to authenticated;
create policy "read own AT snapshot" on public.at_snapshots for select to authenticated using (auth.uid() = user_id);
create policy "insert own AT snapshot" on public.at_snapshots for insert to authenticated with check (auth.uid() = user_id and revision = 1);
create or replace function public.at_compare_and_swap(expected_revision bigint, next_document jsonb)
returns bigint language plpgsql security definer set search_path = '' as $$
declare changed bigint;
begin
 if auth.uid() is null then raise exception 'not authenticated'; end if;
 if expected_revision < 1 or next_document is null then raise exception 'invalid request'; end if;
 update public.at_snapshots
 set revision = revision + 1, document = next_document, updated_at = now()
 where user_id = auth.uid() and revision = expected_revision
 returning revision into changed;
 if changed is null then raise exception 'sync conflict'; end if;
 return changed;
end $$;
revoke all on function public.at_compare_and_swap(bigint,jsonb) from public, anon;
grant execute on function public.at_compare_and_swap(bigint,jsonb) to authenticated;
