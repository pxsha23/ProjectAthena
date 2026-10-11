"""Prints the fully resolved config for an experiment, after `extends` and any --set overrides."""

import argparse

import yaml

from athena_advisor.config import ConfigError, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="path to a YAML config, relative to ml/ or absolute")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="dotted override")
    args = parser.parse_args()
    try:
        config = load_config(args.config, args.set)
    except ConfigError as exc:
        parser.error(str(exc))
    print(f"# fingerprint: {config.fingerprint()}")
    print(yaml.safe_dump(config.to_dict(), sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
