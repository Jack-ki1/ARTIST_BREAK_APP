# Contributing

Thanks for helping improve Breakout Radar.

## Workflow

1. Create a branch for your change.
2. Keep patches focused and reviewable.
3. Run the relevant tests before opening a pull request.
4. Update docs when behavior or configuration changes.

## Local validation

```bash
cd frontend && npm test
cd backend && python -m pytest
```

## Coding standards

- Prefer small, composable functions and clear naming.
- Keep evidence provenance and source timestamps explicit in data model changes.
- Avoid fabricating audience or popularity metrics without a traceable provider and licence.

## Pull requests

Open a pull request with a brief summary, validation steps, and any operational notes. Include a clear explanation of how the change advances the product's evidence-first workflow.
