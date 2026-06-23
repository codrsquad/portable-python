# Configuration

How portable-python is configured, and how settings are merged and overridden.

* [portable-python.yml](/configuration/portable-python-yml.md) - The config file: sections, per-module keys, path templates, and platform overrides.

Configuration is loaded and merged by [`Config`](/architecture/config.md). The built-in `DEFAULT_CONFIG` provides defaults; user files layer on top, with platform-specific sections winning over generic ones. See also the root [CONFIGURATION.md](https://github.com/codrsquad/portable-python/blob/main/CONFIGURATION.md).
