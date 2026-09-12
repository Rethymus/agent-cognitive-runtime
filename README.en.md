# Agent Cognitive Runtime

[简体中文](README.md) · **English**

> Strong models handle bounded decisions. Economy models execute clear tasks. Evidence connects the two.

A local Cognitive Harness Skill for Codex: persistent memory, task contracts, evidence-based delegation, checkpoint downgrades and per-task call admission. Python 3.11+, standard library only.

## The problem

Long tasks lose constraints. Small models repeat failed approaches. Strong models spend time on routine execution. This project gives the agent a reusable way to retrieve relevant facts, define acceptance, delegate bounded work and verify the result.

This is an executable local prototype. It does not change model weights, establish a measured cost reduction, or prove that Luna matches Sol. Model-independent roles currently have one implemented host adapter: Codex.

## One-paste installation

```text
Install Agent Cognitive Runtime from:
https://github.com/Rethymus/agent-cognitive-runtime

Read README.md and docs/installation.md first. Check Python 3.11+ and my
Codex host's Skill and subagent support. Verify the configured model IDs and
reasoning efforts against my actual host; do not guess unsupported aliases.
Preview the installation, preserve my primary model and local memory,
then install the Skill. Enable global activation and native roles only when
supported. Run tests and doctor, and distinguish verified from unverified
capabilities. Do not enable autonomous Skill promotion or background updates.
```

## Install, use, update

```sh
python -X utf8 scripts/manage.py install
python -X utf8 scripts/manage.py install --apply
python -X utf8 scripts/manage.py doctor
```

The installer defaults to a preview. `--apply` writes the Skill. Optional `--activate` adds a managed global AGENTS.md block; `--with-roles` renders native role files. It never edits config.toml. Existing unmanaged files require a reviewed, explicit adoption. See [installation](docs/installation.md).

Ask Codex to use `$agent-cognitive-runtime` for a complex task, define acceptance, delegate independent execution and verify the result. For updates, inspect the changes, run tests and reinstall. The repository does not update itself.

## How it works

Classify → retrieve → contract → plan → act → verify → reflect. Unknown features trigger a bounded evidence probe. Complex decisions use a strong model; verified execution can return to an economy model. The coordinator retains task ownership and verifies artifacts, evidence and side effects.

The example registry binds economy workers to Luna/xhigh, with max for bounded repairs; strong daily roles use medium/high and hard-problem roles use xhigh/max. These are dated research-environment bindings, not availability guarantees for another account.

The default task budget admits four new child inference rounds, including at most two strong rounds, one frontier round and one max-effort round; three may be in flight. Failures, cancellations and follow-up inference consume slots. The ledger cannot intercept every Codex call or cap the main model's tokens. No automatic primary-model switch is implemented.

## Memory and learning

User, Project, Episodic, Failure, Procedural, Skill Library and Evaluation memory, plus Task checkpoints. SQLite provides revisions, source attribution, TTL, dependency invalidation and deletion. Candidates are excluded from normal retrieval. Store public decision assets, never private chain-of-thought.

Autonomous candidate promotion and publication remain disabled. Teacher critique is evidence to evaluate, not authority to rewrite a Skill.

## Development

```sh
python -X utf8 -m unittest discover -s tests -v
python -X utf8 scripts/check_repository.py
```

Tests cover software invariants, not model quality. CI targets Linux and Windows on Python 3.11/3.12. Registry tests use a fixed research date and independently test expiration; production routing uses the real date.

The full research and operating documentation is currently in Chinese: [architecture](docs/architecture.md), [protocol](docs/protocol.md), [evaluation](docs/evaluation.md), [research](docs/research/README.md), [maintenance](docs/maintenance.md), [troubleshooting](docs/troubleshooting.md).

The [September evidence review](docs/research/evidence-review-2026-09.md) separates published findings, limitations and untested engineering hypotheses. A [claim map](docs/research/evidence-map.json), [eight-experiment research protocol](evals/research-program.json) and [development process](docs/research/development-program.md) support future updates. These are research artifacts, not completed model benchmarks or evidence of quota savings.

## License

Unofficial community project. Not affiliated with OpenAI or Anthropic. [MIT](LICENSE) covers original repository material; external sources retain their own rights.
