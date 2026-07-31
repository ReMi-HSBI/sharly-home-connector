## SHARLY Home Connector - Home Assistant Integration

This repository contains the setup instructions and configuration for developing Home Assistant with the `sharly_home` custom component integrated into a containerized development environment.

### Setup Instructions

#### 1. Clone the Repository

```bash
git clone -b dev git@git.cfads.fh-bielefeld.de:remi/sharly/home.git
```

#### 2. Initialize Submodules

The `sharly_home` custom component includes `sharly.core` as a Git submodule. Initialize and update it from the `home` folder:

```bash
cd home/
git submodule init
git submodule update
```

If you already have the repository cloned, update existing submodules:

```bash
git submodule update --init --recursive
```

### Install Custom Component in Home Assistant

If you are using a standard Home Assistant installation (not the development environment), copy the `sharly_home` custom component to your Home Assistant configuration directory:

#### For Standard Home Assistant Installations

1. Locate the cloned `sharly_home` directory:

```bash
ls -la home/src/sharly_home
```

2. Copy the component to your Home Assistant configuration directory:

```bash
cp -r home/src/sharly_home /path/to/homeassistant/config/custom_components/
```

3. Restart Home Assistant for the custom component to load.

The file structure should look like:

```
config/
└── custom_components/
    └── sharly_home/
        ├── __init__.py
        ├── manifest.json
        └── ...
```

### Setup Instructions Dev Environment
If you want to run the `sharly` custom component in the Home Assistant dev environment continue with the following instructions.

#### 1. [Set up local home assistant development environment](https://developers.home-assistant.io/docs/development_environment/)

#### 2. Configure Python Version

Update the Python version of Home Assistant if needed by editing the file `.python-version`:

```
3.14.2
```

#### 3. Mount Configuration

Configure the Home Assistant dev container to mount the `sharly_home` custom component. In your `.devcontainer/devcontainer.json` add the following mount:

```json
"mounts": [
    "source=your/path/home/src/sharly_home,target=${containerWorkspaceFolder}/config/custom_components/sharly_home,type=bind"
]
```

Replace `your/path/home/src/sharly_home` with the absolute path to your `sharly_home` directory.

#### 4. Optional Configuration

Add following snippet to the .devcontainer.json to change the local port:
```json
  "appPort": [
    "8123:8123",
    "5683:5683/udp"
  ]
```

Add the dev environment to the same sharly-network if it exists:
```json
"runArgs": [
    "--network=sharly-network"
  ]
```

### Running Home Assistant

1. Start the Home Assistant dev container with the mounted custom component
2. Run `python3 -m script.hassfest` only once in the terminal to build the translation files
3. Open the command palette: **Ctrl+P**
4. Type `> Task: Run Task`
5. Select **Run Home Assistant Core**
6. Access the running instance at [`http://localhost:8123`](http://localhost:8123)

### SHARLY Home Configuration

Change the default configuration by editing `const.py`:

```bash
...
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8883
DEFAULT_HTTP_SERVER = "https://sharly-http-node"
DEFAULT_HTTP_PORT = 443
DEFAULT_USERNAME = ""
DEFAULT_PASSWORD = ""
DEFAULT_TOPIC_PREFIX = "sharly/events"
```

### References

- [Home Assistant Repository](https://github.com/home-assistant/core)
- [Set up HA development environment](https://developers.home-assistant.io/docs/development_environment/)
