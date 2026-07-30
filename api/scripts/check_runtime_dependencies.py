"""Verify security-sensitive package floors in the finished runtime image."""

from importlib.metadata import version

MINIMUM_VERSIONS = {
    "msgpack": (1, 2, 1),
    "setuptools": (78, 1, 1),
}


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(".") if part.isdigit())


def main() -> None:
    for package, minimum in MINIMUM_VERSIONS.items():
        installed = version(package)
        assert version_tuple(installed) >= minimum, (
            f"{package} {installed} is below the required security floor "
            f"{'.'.join(str(part) for part in minimum)}"
        )
        print(f"{package} {installed}")


if __name__ == "__main__":
    main()
