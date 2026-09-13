# Agent Cognitive Runtime

[简体中文](README.md) · **English**

> Use memory and delegation when they help. Ground decisions and handoffs in evidence.

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

Ask Codex to use `$agent-cognitive-runtime` when memory, recovery or worthwhile independent delegation helps the task, and verify the result within its scope. For updates, inspect the changes, run tests and reinstall. The repository does not update itself.

## How it works

The Skill offers on-demand memory, delegation and maintenance. Use existing context first; retrieve or probe only when information is missing. Delegate independent work when its expected benefit exceeds handoff and review costs. A strong model can return verified execution to an economy model, or finish a short remainder directly. The coordinator retains ownership and verifies artifacts, evidence and side effects. Conceptual stages do not require every task to traverse a fixed sequence.

The example registry binds economy workers to Luna/xhigh, with max for bounded repairs; strong daily roles use medium/high and hard-problem roles use xhigh/max. These are dated research-environment bindings, not availability guarantees for another account.

The default task budget admits four new child inference rounds, including at most two strong rounds, one frontier round and one max-effort round; three may be in flight. Failures, cancellations and follow-up inference consume slots. The ledger cannot intercept every Codex call or cap the main model's tokens. No automatic primary-model switch is implemented.

## Memory and learning

User, Project, Episodic, Failure, Procedural, Skill Library and Evaluation memory, plus Task checkpoints. SQLite provides revisions, source attribution, TTL, dependency invalidation and deletion. Candidates are excluded from normal retrieval. Store public decision assets, never private chain-of-thought.

Autonomous candidate promotion and publication remain disabled. Teacher critique is evidence to evaluate, not authority to rewrite a Skill.

## Evolving instructions alongside models

Version 0.3.3 incorporates an observed local instruction cleanup and protects customized global activation blocks during upgrades. [Instruction review and ablation design](docs/instruction-evolution.md) records scoped decisions and the unrun H09 comparison; a [review bundle](examples/material-bundles/instruction-review/bundle.json) connects sources to follow-up work. The [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model) and [Eric Provencher's engineering article](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) inform this maintenance; neither establishes this project's quality or savings. Existing paper evidence remains below.

## Papers and research foundations

The table pairs mechanisms reported in papers or research reports with a possible project transfer and its boundary. These are source findings or design inferences, not measurements of this project; implementation behavior, cost and model quality require repository experiments.

| Research direction | Direct paper / research link | Project transfer and boundary |
|---|---|---|
| ReAct: interleaved reasoning and action | [ReAct](https://arxiv.org/abs/2210.03629) | Informs a reasoning–tool–observation loop; the current code verifies protocol and tool receipts, not the paper’s result. |
| Reflexion: reusable reflection from feedback | [Reflexion](https://arxiv.org/abs/2303.11366) | Informs storing failure receipts and reflections as candidate evidence; automatic promotion remains disabled and needs independent acceptance. |
| Self-Refine: feedback driven iterative revision | [Self-Refine](https://arxiv.org/abs/2303.17651) | Supports separating generation, review and revision into checkable steps; self review is not correctness, so use deterministic tests or calibrated review. |
| Voyager: skill library and curriculum style accumulation | [Voyager](https://arxiv.org/abs/2305.16291) | Informs the Skill Library and procedural assets; transfer to Codex tools and projects requires task separation and negative controls. |
| Procedural and workflow memory | [Agent Workflow Memory](https://arxiv.org/abs/2409.07429) · [Managing Procedural Memory](https://arxiv.org/html/2606.23127v1) | Organize experience at workflow, subtask and function granularity; scope, versioning and refusal when inapplicable still require project validation. |
| Weak-to-strong supervision | [Weak-to-Strong Generalization](https://arxiv.org/abs/2312.09390) | Studies training a strong learner under weak supervision; this differs from strong-teacher guidance of an economy worker and does not establish weight updates through a Skill. |
| Test-time compute and additional reasoning | [Scaling LLM Test-Time Compute](https://arxiv.org/abs/2408.03314) · [Inverse Scaling](https://alignment.anthropic.com/2025/inverse-scaling/) · [When More Thinking Hurts](https://arxiv.org/abs/2604.10739) | Supports pairing model and effort separately and counting routing cost; paper task and model boundaries cannot be converted into Codex effort or savings. |
| RouteLLM: preference data based model routing | [RouteLLM](https://arxiv.org/abs/2406.18665) | Informs model selection comparisons; the current router remains rule and evidence gated, with no claimed preference routing benefit. |
| EvoAgentBench: ability transfer and agent self evolution | [EvoAgentBench](https://arxiv.org/html/2607.05202v1) | Supports testing Skill transfer on new instances, tool changes and negative controls; an Anchor or ability label is not deployment routing evidence. |
| AMD (Agent Memory Distillation) | [Agent Memory Distillation](https://arxiv.org/html/2608.07169v1) | Informs teacher workflow, subtask and function assets; static offline memory and limited tool tasks do not establish this project’s online effect. |
| MemGym and StreamMemBench: long horizon and streaming memory | [MemGym](https://arxiv.org/html/2605.20833v1) · [StreamMemBench](https://arxiv.org/html/2606.14571v2) | Separate retention, first use, feedback absorption and later reuse; synthetic tasks and personal streams do not directly generalize to code tasks. |
| MemSyco-Bench: sycophancy and memory misuse | [MemSyco-Bench](https://arxiv.org/html/2607.01071v2) | Test whether relevant but wrong, stale or cross project memories induce errors; synthetic dialogues do not provide real world incidence. |
| Evaluator reliability and self correction | [LLMs Cannot Self-Correct Reasoning](https://arxiv.org/abs/2310.01798) · [Key Condition Verification](https://arxiv.org/abs/2405.14092) · [Demystifying evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) · [LLM-as-a-Judge](https://arxiv.org/html/2609.02246v1) · [Self-Preference Evaluations](https://arxiv.org/html/2601.22548v4) | Treat a judge as evidence requiring calibration and keep deterministic gates first; the reports do not show that this project’s evaluator is reliable. |
| Evaluation integrity, reward hacking and infrastructure noise | [Infrastructure noise](https://www.anthropic.com/engineering/infrastructure-noise) · [Eval awareness](https://www.anthropic.com/engineering/eval-awareness-browsecomp) · [Hack-Verifiable Environments](https://arxiv.org/html/2605.20744v1) | Isolate answers, graders and holdout sets while recording environment and cost; the local implementation does not yet provide an independent execution boundary. |

Normative and engineering documents (not papers): [Agent Skills Specification](https://agentskills.io/specification) · [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents). The complete source list, reading scope and limitations are in [sources.json](docs/research/sources.json); claims and experiments map directly in [evidence-map.json](docs/research/evidence-map.json).

## Evolve from new models and materials

Use the [material-driven maintenance guide](docs/material-evolution.md) to turn model cards, papers, tool documentation, datasets, examples and evaluation records into versioned review bundles. `scripts/materials.py` implements `init`, `check`, `plan` and `impact`: references, snapshot hashes, evidence gaps, proposed file baselines, within-bundle dependency impact and cross-split fingerprint/group checks. It does not execute source instructions, change model bindings or promote candidates.

```sh
python -X utf8 scripts/materials.py plan examples/material-bundles/teacher-assets/bundle.json
python -X utf8 scripts/materials.py plan examples/material-bundles/future-model/bundle.json
```

The future-model example deliberately reports missing evidence. See the [bundle schema](schemas/material-bundle.schema.json), [Model Cards](https://arxiv.org/abs/1810.03993), [Datasheets for Datasets](https://arxiv.org/abs/1803.09010) and [PROV overview](https://www.w3.org/TR/prov-overview/). Documentation and byte-level validation do not establish model quality or permission to publish.

## Development

```sh
python -X utf8 -m unittest discover -s tests -v
python -X utf8 scripts/check_repository.py
```

Tests cover software invariants, not model quality. CI targets Linux and Windows on Python 3.11/3.12. Registry tests use a fixed research date and independently test expiration; production routing uses the real date.

The full research and operating documentation is currently in Chinese: [architecture](docs/architecture.md), [protocol](docs/protocol.md), [evaluation](docs/evaluation.md), [research](docs/research/README.md), [maintenance](docs/maintenance.md), [troubleshooting](docs/troubleshooting.md).

The [September evidence review](docs/research/evidence-review-2026-09.md) separates published findings, limitations and untested engineering hypotheses. A [claim map](docs/research/evidence-map.json), [nine-experiment research protocol](evals/research-program.json) and [development process](docs/research/development-program.md) support future updates. These are research artifacts, not completed model benchmarks or evidence of quota savings.

## License

Unofficial community project. Not affiliated with OpenAI or Anthropic. [MIT](LICENSE) covers original repository material; external sources retain their own rights.
