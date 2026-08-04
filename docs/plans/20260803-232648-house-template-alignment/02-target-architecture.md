# Target Architecture

Four edges change. Nothing else does.

## A. Configuration Through One App-Owned XCFG Adapter

### Placement

Configuration stays inside the `workspace` capability, which already owns
it, as sibling modules rather than a new top-level package:

```text
libs/workspace/
|-- settings.py     # the strict Settings model (today's StaticConfig)
|-- loader.py       # the only module importing xcfg
|-- marker.py       # workspace identity  (delta B)
|-- resolver.py     # root resolution     (delta B)
|-- paths.py        # typed derived paths (delta B)
|-- config.py       # deleted at the end of Stone 4
```

The template's `configuration/` package is a shape, not a requirement; it
also says a small capability may use four modules rather than a
directory. The existing Import Linter contract "Workspace and
configuration do not depend on runtime capabilities" already names this
capability as the configuration owner.

### Spec

```python
SPEC = ConfigSpec(
    config_root=resource_path("config"),
    env_prefix="XQUEUE_",
    app_name="xqueue",
    project_dir=".xqueue",
    config_name="config.yaml",
    env_extends_default=True,
)
```

`profiled_sections` stays empty. Profiles solve independently varying
dimensions such as model or storage backends; xqueue has one backend and
one storage engine, so a profile directory would be an empty mechanism.
Add it when a second dimension is real.

### Precedence contract

```text
base:   explicit --config / XQUEUE_CONFIG
        > packaged config.<env>.yaml selected by --env / XQUEUE_ENV
        > packaged config.default.yaml

merge:  base
        < ~/.config/xqueue/config.yaml
        < <workspace>/.xqueue/config.yaml
        < XQUEUE_<SECTION>__<KEY>
        < --set path=value
```

`env_extends_default=True` makes a named environment file an overlay, so
it states only what it changes.

`resources/config/config.default.yaml` becomes the single written
statement of every default. Field defaults stay on the model as the
programmatic contract; the packaged file is what an operator reads and
copies.

### Error mapping

`libs/core/errors.py` gains `ConfigurationError(XqueueError)`. The
adapter catches `xcfg.ConfigError` and re-raises it. No `xcfg` symbol
appears in any xqueue signature, result model, or raised type. The CLI
maps `ConfigurationError` to exit code 2 — invalid usage — because every
path to it is a bad file, a bad key, or a bad override.

### Environment compatibility

Unchanged and app-owned, because each names a location rather than a
settings value:

| Variable | Meaning | Owner |
| --- | --- | --- |
| `XQUEUE_ROOT` | workspace root selector (new) | resolver |
| `XQUEUE_HOME` | home instance state root | resolver |
| `XQUEUE_DB_PATH` | Alembic target during reset | instance |
| `XQUEUE_LOG_LEVEL` | process logging | runtime |
| `XQUEUE_LOG_FORMAT` | process logging | runtime |

XCFG cannot claim any of these: its environment layer skips variables
without the `__` delimiter. `XQUEUE_CONFIG` and `XQUEUE_ENV` are reserved
by the spec and excluded from the override layer by XCFG itself.

## B. Validated Workspace Identity

### Marker

`<root>/.xqueue/marker.toml`:

```toml
kind = "xqueue-workspace"
schema = 1
created_by = "xqueue 0.1.0"
```

The marker states product identity and workspace schema only. The
database migration head stays in Alembic, which owns it.

### Scope model

xqueue keeps two scopes, and this is the decision that differs from a
plain reading of the template:

- the **home instance** (`XQUEUE_HOME` or `~/.xqueue`) is the default,
  because the product is one machine-wide queue whose controller
  supervises pools for many projects; and
- a **workspace instance** (`<root>/.xqueue/`) is selected when a valid
  marker is found or an explicit root is given.

Absence of a workspace is therefore not an error — it selects the home
instance. A *malformed*, wrong-product, or unsupported-schema marker is
always a typed error with a recovery hint, never a silent fallback to
home. That is the distinction the template actually draws.

### Resolution order

```text
explicit workspace_root argument or --workspace
  > XQUEUE_ROOT
  > nearest parent directory holding a valid .xqueue/marker.toml
  > home instance
```

Discovery walks up from a caller-supplied start directory, never
implicitly from `Path.cwd()`. `apps/cli/client.py` remains the one place
that supplies `Path.cwd()` as that start directory, which is a channel
convenience rather than ambient state.

### Typed workspace

```python
@dataclass(frozen=True)
class Workspace:
    root: Path
    directory: Path
    marker: WorkspaceMarker
```

`RuntimePaths` is derived from it rather than assembled from loose
arguments, and `Runtime` receives the `Workspace` plus validated
`Settings`. Capability code never rediscovers a root and never reads the
process environment for one.

### `xq workspace init`

A management-plane action: creates the marker, `config.yaml`, and the
directory skeleton; idempotent when existing content is compatible;
returns a typed change set of created, retained, and conflicting paths;
never overwrites configuration without `--force`; writes atomically;
updates ignore rules additively; and refuses an unsupported schema with a
documented migration path.

Migration policy follows the template's table: the SDK refuses, the CLI
previews and requires explicit intent.

### Retiring `--workspace-instance`

The hidden flag becomes redundant: `<repo>/instance/` is exactly a
workspace instance under a different name. Stone 3 maps it onto
`.xqueue/`, keeps the flag as a deprecated alias for one release, and
deletes the second resolution branch in `resolve_paths`.

## C. Packaging

```toml
[project]
dependencies = [
  "alembic>=1.16.5",
  "pydantic>=2.11.9",
  "pyyaml>=6.0.3",
  "sqlalchemy>=2.0.43",
  "structlog>=25.4.0",
  "xcfg==0.4.1",
]

[project.optional-dependencies]
cli = ["typer>=0.16.1", "rich>=14.1.0", "python-toon>=0.1.3"]
all = ["xqueue[cli]"]
```

`xq` stays declared. `xqueue_cli.main:main` guards its framework imports
and, when they are absent, writes one line to stderr —
`xq requires the cli extra: pip install "xqueue[cli]"` — and exits 2.
An `ImportError` traceback is not an acceptable operator contract.

Documented install for operators becomes `uv tool install "xqueue[cli]"`;
for embedders, `xqueue`.

XCFG is pinned to an exact released tag, not a range, until the house has
a policy for its compatibility.

## D. Declared Artifacts With Gates

### Plane map

`PLANE-MAP.md` ships in this plan directory, completed against the real
actions, and moves to `docs/dev/` when Stone 1 lands. Its purpose here is
not classification for its own sake: it is where the multiple-writers
question about the `jobs` table gets answered.

### Channel parity matrix

`docs/dev/channel-parity.md` holds one row per capability operation:

```text
| Operation | SDK | CLI | Contract | Plane | Omission reason |
```

`tests/architecture/test_channel_parity.py` parses that table and
asserts, in both directions:

- every public method on every SDK facet appears exactly once;
- every name in `COMMAND_CONTRACTS` appears exactly once; and
- every row marked as exposed on a channel names a real method or
  contract.

A new facet method or a new contract then fails the suite until the
matrix records it, including its plane and its intentional omissions.
This is the mechanism that keeps the document true; without it the
matrix decays in one sprint.

## Guardrails Added

Three new rules, in the existing fail-closed style:

1. Import Linter — only `xqueue.workspace.loader` may import `xcfg`.
2. Semgrep — `os.environ` and `getenv` are an error outside
   `libs/workspace/resolver.py`, `libs/workspace/instance.py`,
   `libs/runtime/logging.py`, and `libs/workers/process.py`, which is the
   template's "only the configuration adapter reads process environment
   for settings" expressed as an allowlist.
3. Boundary checker — capability modules may not import
   `xqueue.workspace.resolver`; a root is passed in, never rediscovered.
