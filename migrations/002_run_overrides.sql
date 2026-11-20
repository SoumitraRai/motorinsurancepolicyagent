-- Reviewer-supplied facts for a clarification rerun (SR25). Null for ordinary uploads.
alter table runs add column if not exists overrides jsonb;
