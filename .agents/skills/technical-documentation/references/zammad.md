# Zammad MCP Documentation Overlay

Use this overlay for documentation in `basher83/Zammad-MCP`.
It supplements the shared skill. Root and nearest-scope `AGENTS.md` instructions still govern the work.
Recheck the named files before relying on their current behavior or commands.

## Route readers by task

This repository uses Markdown pages and relative links. Inspect existing navigation before proposing a documentation framework.

| Surface | Reader purpose |
|---|---|
| `README.md` | Understand the server, install it, configure it, and reach a first working result |
| `docs/deployment/http-transport.md` | Deploy HTTP transport and troubleshoot access |
| `CONTRIBUTING.md` | Set up development, validate changes, and contribute |
| `ARCHITECTURE.md` | Understand components, boundaries, and design constraints |
| `SECURITY.md` | Find security policy and reporting instructions |
| `CHANGELOG.md` | Find release history |
| `docs/plans/`, `docs/audits/`, `docs/reviews/`, `docs/bug-reports/` | Read dated plans and evidence, not assume current behavior |
| `docs/ai-docs/`, `docs/dev/` | Consult tooling references and developer notes within their stated scope |

Keep one recommended setup path near the start of the README.
Link detailed deployment and contributor procedures from the relevant entry section.
Keep essential prerequisites and safety conditions beside the commands they qualify.
Do not turn historical plans into current instructions without checking implementation and release evidence.

## Choose the page shape

- **Overview:** purpose, audience, supported use, first working example, and links to detailed tasks.
- **How-to:** outcome, prerequisites, steps, expected result, verification, and troubleshooting.
- **Reference:** names, types, defaults, required values, constraints, errors, and examples.
- **Explanation:** responsibilities, boundaries, tradeoffs, and links to procedures.
- **Troubleshooting:** observable symptom, diagnostic check, evidence-based cause, and recovery steps.

Keep commands complete enough to use. Label placeholders and use synthetic credentials.
State what a check proves. Successful startup alone does not prove a Zammad operation succeeds.

## Ground claims in the repository

Paths in this overlay are relative to the repository root.

| Claim | Inspect before writing |
|---|---|
| Installed command and Python support | `pyproject.toml`, `mcp_zammad/__main__.py` |
| Transport selection, host, and port | `mcp_zammad/config.py`, `mcp_zammad/server.py`, `tests/test_config.py` |
| Zammad authentication and secret-file inputs | `mcp_zammad/client.py`, `.env.example`, controlled client tests |
| MCP tools, resources, and prompts | `mcp_zammad/server.py`, public MCP behavior, applicable tests |
| Field validation and response contracts | `mcp_zammad/models.py`, applicable model and client tests |
| HTTP behavior | `tests/integration/test_http_transport.py`, server lifecycle code |
| Container configuration | `Dockerfile`, `docker-compose.yml`, `.github/workflows/docker-publish.yml` |
| Developer commands and gates | `mise.toml`, `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/` |

Distinguish inspected implementation, executed tests, released behavior, proposals, and maintainer intent.
For release claims, identify the release and supporting tag or artifact. The current checkout alone is insufficient.
Check dependency documentation or source for dependency-specific defaults and guarantees.
When instructions and executable configuration disagree, report both sources and the observed mismatch.
Do not copy an old mismatch into new docs without checking it again.
Documentation work does not authorize changing repository policy or automation to resolve that disagreement.

## Preserve configuration and security meaning

Check transport defaults and requirements against implementation before changing examples.
Keep upstream Zammad credentials distinct from inbound MCP client authentication.
Keep TLS verification, explicit insecure-mode conditions, and listener exposure warnings beside affected examples.
Do not infer comprehensive SSRF or XSS protection from individual validation or escaping functions.
Use `.env.example` for documented variable names. Do not inspect real secret files to construct examples.
Use controlled tests for behavior checks. Live Zammad access requires separate authorization.

For rewrites and splits, apply [preservation mapping](preservation.md).
Map authentication alternatives, defaults, security warnings, commands, and troubleshooting as separate source units.
Preserve existing Markdown links and heading fragments using syntax allowed by `.rumdl.toml`.
That configuration restricts HTML. Do not introduce raw anchor stubs without checking the renderer and lint policy.

## Check the touched surface

Inspect the current task and hook definitions first. Run commands from the repository root.
Use explicit changed paths, including new files, for scoped checks:

```bash
prek run rumdl --files <changed-markdown-paths>
uv run --no-project .agents/skills/technical-documentation/scripts/ste-lint.py --summary <changed-markdown-paths>
git diff --check
```

Replace placeholders with actual paths. Use `--mode flavored` for explanation and README prose, or `--max-words 20` for procedures.
Record the STE baseline before editing existing prose. Hard violations must not increase.
Check Rumdl exclusions and the files actually processed. A skipped file has no check result.
Check relative links, fragments, examples, and preservation mappings separately.
Use `mise run markdown-lint` when the requested scope warrants all tracked Markdown files.

Run focused controlled tests when changed docs make behavior claims that need execution evidence.
For example, use `uv run pytest tests/test_config.py` for transport configuration claims.
Inspect the test selection and report what ran. Do not claim deployment verification from static checks.
Report unavailable tools, failed checks, skipped files, and checks not run.
Do not claim local/CI parity without comparing and exercising the applicable gates.

`mise run markdown-fix`, `mise run pre-commit-run`, and `./scripts/quality-check.sh` can change files.
Do not use them for read-only validation.
For requested changelog work, use `mise run changelog` or `mise run changelog-bump <version>` as applicable.
Preserve released history and follow the repository's changelog instructions.
