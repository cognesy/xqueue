# xqueue

`xqueue` (`xq`) is a CLI-first, single-machine durable work queue for running
shell commands.

## Documentation

- Operator guides: [docs/user/README.md](/Users/ddebowczyk/projects/xqueue/docs/user/README.md)
- Developer workflow: [docs/dev/README.md](/Users/ddebowczyk/projects/xqueue/docs/dev/README.md)
- Product specification: [SPEC.md](/Users/ddebowczyk/projects/xqueue/SPEC.md)

## Development

```sh
uv sync
uv run xq --help
uv run pytest
```

See [SPEC.md](/Users/ddebowczyk/projects/xqueue/SPEC.md) for the product
specification and [xqueue-spec-implementation.md](/Users/ddebowczyk/projects/xqueue/docs/dev/plans/xqueue-spec-implementation.md)
for the current implementation plan.
