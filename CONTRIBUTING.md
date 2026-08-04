# Contributing

This document describes how to set up the SHARLY Home development environment.

## Development Environment

The project is developed using the official Home Assistant development environment.

### Clone the repository

```bash
git clone git@github.com:ReMi-HSBI/sharly-home-connector.git
```

## Initialize submodules

The `sharly_home` custom component includes `sharly.core` as a Git submodule.

From the repository root run:

```bash
git submodule init
git submodule update
```

If the repository is already cloned:

```bash
git submodule update --init --recursive
```

## Set up the Home Assistant development environment

Follow the official Home Assistant documentation:

https://developers.home-assistant.io/docs/development_environment/

## Configure the devcontainer

### Mount the custom component

Add the following mount to `.devcontainer/devcontainer.json`:

```json
"mounts": [
    "source=/absolute/path/home/src/sharly_home,target=${containerWorkspaceFolder}/config/custom_components/sharly_home,type=bind"
]
```

Replace the source path with your local repository path.

### Optional configuration

Expose additional ports:

```json
"appPort": [
    "8123:8123", # e.g. "8124:8123"
    "5683:5683/udp"
]
```

Connect the development container to the SHARLY Docker network:

```json
"runArgs": [
    "--network=sharly_sharly-network"
]
```

## Running Home Assistant

1. Start the Home Assistant development container.
2. Run:

```bash
python3 -m script.hassfest
```

This only needs to be executed once to generate the translation files.

3. Open the Command Palette (`Ctrl+Shift+P`).
4. Select **> Tasks: Run Task**.
5. Choose **Run Home Assistant Core**.
6. Open:

```
http://localhost:8123
```

## Development Configuration

Default values can be adjusted in `const.py`:

```python
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8883
DEFAULT_HTTP_SERVER = "https://sharly-http-node"
DEFAULT_HTTP_PORT = 443
DEFAULT_USERNAME = ""
DEFAULT_PASSWORD = ""
DEFAULT_TOPIC_PREFIX = "sharly/events"
```

## References

- [Home Assistant Repository](https://github.com/home-assistant/core)
- [Set up HA development environment](https://developers.home-assistant.io/docs/development_environment/)
