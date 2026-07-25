# CLI commands

All commands assume you're in `/Users/vmac/prog/DJANGO/riskregister` and run
through `uv run` so they use the project's managed virtualenv.

## Setup

```bash
uv sync                                # install/sync dependencies from uv.lock
uv run python manage.py migrate        # apply migrations to db.sqlite3
uv run python manage.py createsuperuser # create your admin login
```

## Day to day

```bash
uv run python manage.py runserver      # start the dev server on :8000
uv run python manage.py check          # system check (catches config errors fast)
```

## Data

```bash
uv run python manage.py seed_demo         # populate demo departments/categories/risks
uv run python manage.py seed_demo --flush # wipe seeded rows and regenerate them
```

Seeding is idempotent for departments/categories (matched by name) and skips
risks that already exist by title, so re-running without `--flush` just fills
in anything missing rather than duplicating.

All seeded content — department/category names, risk titles, descriptions,
mitigation action plans — lives in `risks/seed_data.yaml`, not in the
command. Edit that file to change what gets seeded; no Python changes
needed.

## Migrations (after editing models.py)

```bash
uv run python manage.py makemigrations risks  # generate a new migration
uv run python manage.py migrate               # apply it
uv run python manage.py showmigrations risks  # see what's applied vs pending
```

## Dependencies (uv)

```bash
uv add <package>       # add and install a new dependency
uv add --dev <package> # add a dev-only dependency (e.g. a linter)
uv remove <package>    # remove a dependency
```

## Other useful built-ins

```bash
uv run python manage.py shell     # interactive Python shell with Django loaded
uv run python manage.py dbshell   # open a sqlite3 shell on db.sqlite3
```
