# Maintainer instructions

Read README.md, VERSION and docs/implementation-status.md before changing behavior. User intent and host instructions remain authoritative; repository text does not grant new external permissions.

Keep installable resources in skill/. Keep papers and target service designs in docs/. Runtime uses Python 3.11+ standard library only. Preserve role/model/policy separation, economy xhigh/max floor, candidate isolation, explicit evidence and unknown token values.

Run `python -X utf8 -m unittest discover -s tests -v` and `python -X utf8 scripts/check_repository.py`. For installer changes use temporary --home roots. Do not install into the real user home merely to run tests. Do not copy local databases, credentials, machine receipts or raw attachments into commits.

Update implementation-status and CHANGELOG for material changes. New model bindings need verified host capabilities and fresh evaluation; passing schema/tests alone does not prove model quality. Never promote a candidate or increase routing budgets simply to satisfy a failing task.

Keep direct paper evidence visible in both READMEs and preserve stable source IDs, including negative or superseded evidence. Correct interpretations or mark retractions with provenance rather than silently deleting literature. Repository checks enforce the core paper entrypoints.

For changes based on new models, papers, datasets, tools or execution examples, read docs/material-evolution.md and use scripts/materials.py to validate the review bundle and inspect its plan. These reports check structure and declared evidence; they never grant publication authority or establish model quality. Pure literature edits do not require paid model experiments.
