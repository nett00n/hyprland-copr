-- HyperMnesia Tier 0/1 seed for hyprland-copr-daily (#COPR-0024).
--
-- CLAUDE.md is the source of truth. This file is a hand-maintained projection of it into
-- HyperMnesia's component/constraint schema -- edit CLAUDE.md first, then update this file to
-- match. Load with:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f memory/seed.sql
-- Repo-scoped + idempotent: resets only repo='hyprland-copr-daily'.

BEGIN;
DELETE FROM constraints   WHERE repo='hyprland-copr-daily';
DELETE FROM relationships WHERE src_component_id IN (SELECT id FROM components WHERE repo='hyprland-copr-daily');
DELETE FROM components    WHERE repo='hyprland-copr-daily';

-- Parent (organizational; empty key_paths -> not path-resolved, just groups the map).
INSERT INTO components (repo,slug,name,parent_id,responsibility,key_paths,priority,owner) VALUES
('hyprland-copr-daily','copr-root','hyprland-copr-daily',NULL,
 'Automates maintaining the Hyprland Fedora Copr repo.','{}'::text[],10,'you');

-- Leaves (path-resolved via key_paths globs; higher priority wins on glob overlap).
INSERT INTO components (repo,slug,name,parent_id,responsibility,key_paths,priority,owner) VALUES
('hyprland-copr-daily','copr-pipeline','Build pipeline stages',
 (SELECT id FROM components WHERE slug='copr-root' AND repo='hyprland-copr-daily'),
 'spec -> vendor -> srpm -> mock -> copr stage scripts and the full-cycle/matrix drivers.',
 ARRAY['scripts/stage-*.py','scripts/full-cycle.py'],30,'you'),
('hyprland-copr-daily','copr-lib','Shared library',
 (SELECT id FROM components WHERE slug='copr-root' AND repo='hyprland-copr-daily'),
 'scripts/lib/** -- path resolution, build-report.db, YAML config, vendoring, reporting.',
 ARRAY['scripts/lib/**'],35,'you'),
('hyprland-copr-daily','copr-config','Package manifests',
 (SELECT id FROM components WHERE slug='copr-root' AND repo='hyprland-copr-daily'),
 'packages.yaml (source of truth), groups.yaml, repo.yaml, sources.lock.yaml.',
 ARRAY['packages.yaml','groups.yaml','repo.yaml','sources.lock.yaml'],35,'you'),
('hyprland-copr-daily','copr-templates','Jinja templates',
 (SELECT id FROM components WHERE slug='copr-root' AND repo='hyprland-copr-daily'),
 'Spec/README/docs templates rendered by the pipeline; the generated files are not the source.',
 ARRAY['templates/**'],30,'you'),
('hyprland-copr-daily','copr-vendored','Vendored submodules',
 (SELECT id FROM components WHERE slug='copr-root' AND repo='hyprland-copr-daily'),
 'Upstream sources checked out as git submodules for packaging.',
 ARRAY['submodules/**'],40,'you'),
('hyprland-copr-daily','copr-docs','Docs',
 (SELECT id FROM components WHERE slug='copr-root' AND repo='hyprland-copr-daily'),
 'FRD/feature docs, operations runbook, CLAUDE.md, README.',
 ARRAY['docs/**','CLAUDE.md','README.md'],25,'you'),
('hyprland-copr-daily','copr-tests','Tests',
 (SELECT id FROM components WHERE slug='copr-root' AND repo='hyprland-copr-daily'),
 'Unit and integration tests for scripts/.',
 ARRAY['tests/**'],25,'you');

-- Relationships (dependency graph; constraint propagation is one hop, either direction).
INSERT INTO relationships (src_component_id,dst_component_id,kind)
SELECT (SELECT id FROM components WHERE slug=s AND repo='hyprland-copr-daily'),
       (SELECT id FROM components WHERE slug=d AND repo='hyprland-copr-daily'), k
FROM (VALUES
  ('copr-pipeline','copr-lib','depends_on'),
  ('copr-pipeline','copr-config','depends_on'),
  ('copr-pipeline','copr-templates','depends_on')
) AS t(s,d,k);

-- Constraints (invariant | convention; severity must | should | info; global or a component).
-- source_doc_id left NULL: CLAUDE.md/docs/DOCS-DRIVEN-DEVELOPMENT.md are not (yet) ingested
-- documents with a stable id at seed-authoring time; re-link once ingest has run once, if
-- freshness tracking on these constraints is wanted.
INSERT INTO constraints (repo,kind,scope,component_id,title,statement,rationale,severity) VALUES
('hyprland-copr-daily','invariant','global',NULL,
 'Never git commit',
 'Do not run `git commit` (or anything that commits) unless the operator explicitly asks. When a task is ready and tested, report to the operator: what changed, a before/after example, and a sample commit message -- let them commit.',
 'CLAUDE.md is explicit: report and hand off, don''t commit.','must'),
('hyprland-copr-daily','invariant','global',NULL,
 'packages.yaml is the source of truth',
 'Every feature/field packages.yaml exposes must exist in packages.yaml.example. Do not hand-author package state anywhere else.',
 'Prevents a second, drifting source of package configuration.','must'),
('hyprland-copr-daily','invariant','global',NULL,
 'Never bump the manifest version by hand',
 'Package versions in packages.yaml are set by `scripts/update-versions.py` / `make update-versions`, not edited directly.',
 'Manual bumps skip the upstream-tag verification the automation performs.','must'),
('hyprland-copr-daily','invariant','component',
 (SELECT id FROM components WHERE slug='copr-vendored' AND repo='hyprland-copr-daily'),
 'Vendored sources are read-only',
 'Do not edit files under submodules/ directly. Any change to upstream source needs a pre-build action in packages.yaml instead.',
 'Direct edits are silently discarded the next time the submodule is synced/updated.','must'),
('hyprland-copr-daily','invariant','component',
 (SELECT id FROM components WHERE slug='copr-tests' AND repo='hyprland-copr-daily'),
 'Run checks before and after changes, via make targets',
 'Run the relevant `make` targets (test/lint/fmt/validate-packages) both before and after making changes, not just after. Do not invoke pytest/ruff/etc. directly when a make target exists for it.',
 'Catches a check that was already failing before your change, and keeps the container/venv setup consistent.','must'),
('hyprland-copr-daily','convention','component',
 (SELECT id FROM components WHERE slug='copr-lib' AND repo='hyprland-copr-daily'),
 'Every top-level function/class carries its #COPR-NNNN',
 'Each top-level function or class implementing a feature names the #COPR-NNNN id(s) it implements, as a comment directly above it or the first line of its docstring.',
 'Keeps code traceable back to the feature doc that specifies its behavior.','should'),
('hyprland-copr-daily','convention','component',
 (SELECT id FROM components WHERE slug='copr-docs' AND repo='hyprland-copr-daily'),
 'Docs-driven development order',
 'Changed behavior edits the existing feature document first; new behavior gets a new #COPR-NNNN id and a new doc under docs/features/, before the code. Follow docs/DOCS-DRIVEN-DEVELOPMENT.md.',
 'Docs are the contract; code proves it.','should'),
('hyprland-copr-daily','convention','component',
 (SELECT id FROM components WHERE slug='copr-templates' AND repo='hyprland-copr-daily'),
 'Edit the template, not the generated file',
 'Generated files (specs, README shells, docs) come from templates/**. Edit the template and regenerate rather than hand-editing the output.',
 'A hand-edit is overwritten by the next generation run without warning.','should');
COMMIT;
