set -eu

export RUFF_CACHE_DIR="${RUFF_CACHE_DIR:-/tmp/ruff}"
export MYPY_CACHE_DIR="${MYPY_CACHE_DIR:-/tmp/mypy}"
export COVERAGE_FILE="${COVERAGE_FILE:-/tmp/.coverage}"

ruff check app tests alembic
ruff format --check app tests alembic
mypy app
coverage run --source=app -m pytest --no-cov -o cache_dir=/tmp/pytest
coverage report --show-missing --fail-under=80
