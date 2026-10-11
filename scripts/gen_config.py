"""Generate C++ config headers from config/config_<node>.yaml.

Runs automatically before every PlatformIO build (extra_scripts in platformio.ini).
Can also be run by hand from the repo root: python3 scripts/gen_config.py

config/config_<node>.yaml  ->  lib/arctos_board/<node>_config.h

Mapping, using node "gripper":
  section.key                ->  GRIPPER_SECTION_KEY
  boards.<board>.pins.<key>  ->  GRIPPER_PIN_KEY  (inside #if for that board)
  boards.<board>.<key>       ->  GRIPPER_KEY      (inside #if for that board)
  null                       ->  left out, listed as unset
  host: ...                  ->  skipped (settings only the PC-side tools use)
"""

import os
import subprocess
import sys

# Preprocessor test for each board key allowed under `boards:`.
BOARD_CONDITIONS = {
    "nano": "defined(ARDUINO_ARCH_AVR)",
    "esp32": "defined(ARDUINO_ARCH_ESP32)",
}


def load_yaml(path, python_exe=sys.executable):
    try:
        import yaml
    except ImportError:
        print("gen_config: installing PyYAML into", python_exe)
        subprocess.check_call([python_exe, "-m", "pip", "install", "-q", "pyyaml"])
        import yaml
    with open(path) as f:
        return yaml.safe_load(f) or {}


def cpp_constant(name, value, is_pin=False):
    if value is None:
        return f"// {name}: unset (null in config)"
    if isinstance(value, bool):
        return f"constexpr bool {name} = {'true' if value else 'false'};"
    if isinstance(value, int):
        if is_pin:
            return f"constexpr uint8_t {name} = {value};"
        if name.endswith("_ID"):
            return f"constexpr uint32_t {name} = 0x{value:02X};"
        return f"constexpr long {name} = {value};"
    if isinstance(value, float):
        return f"constexpr float {name} = {value}f;"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'constexpr char {name}[] = "{escaped}";'
    raise ValueError(f"{name}: unsupported value {value!r} (use numbers, strings, booleans or null)")


def flatten(prefix, data):
    """Yield (CONSTANT_NAME, value) for every leaf of a nested mapping."""
    for key, value in data.items():
        name = f"{prefix}_{key}".upper()
        if isinstance(value, dict):
            yield from flatten(name, value)
        else:
            yield name, value


def render(node, config, source):
    prefix = node.upper()
    lines = [
        f"// GENERATED from {source} by scripts/gen_config.py. Do not edit;",
        "// change the YAML and rebuild (or run the script).",
        "#pragma once",
        "",
        "#include <stdint.h>",
        "",
    ]

    config.pop("host", None)
    boards = config.pop("boards", {}) or {}
    for name, value in flatten(prefix, config):
        lines.append(cpp_constant(name, value))

    if boards:
        unknown = set(boards) - set(BOARD_CONDITIONS)
        if unknown:
            raise ValueError(f"unknown board(s) {sorted(unknown)}; known: {sorted(BOARD_CONDITIONS)}")
        lines.append("")
        directive = "#if"
        for board, settings in boards.items():
            lines.append(f"{directive} {BOARD_CONDITIONS[board]}  // {board}")
            settings = dict(settings or {})
            for key, value in (settings.pop("pins", {}) or {}).items():
                lines.append(cpp_constant(f"{prefix}_PIN_{key}".upper(), value, is_pin=True))
            for name, value in flatten(prefix, settings):
                lines.append(cpp_constant(name, value))
            directive = "#elif"
        lines.append("#else")
        lines.append(f'#error "No {node} config for this board: add it under boards: in {source}"')
        lines.append("#endif")

    return "\n".join(lines) + "\n"


def generate_all(project_dir, python_exe=sys.executable):
    config_dir = os.path.join(project_dir, "config")
    out_dir = os.path.join(project_dir, "lib", "arctos_board")
    for filename in sorted(os.listdir(config_dir)):
        if not (filename.startswith("config_") and filename.endswith(".yaml")):
            continue
        node = filename[len("config_"):-len(".yaml")]
        source = f"config/{filename}"
        header = render(node, load_yaml(os.path.join(config_dir, filename), python_exe), source)
        out_path = os.path.join(out_dir, f"{node}_config.h")
        # Only write on change so unchanged configs don't trigger a rebuild.
        if os.path.exists(out_path) and open(out_path).read() == header:
            continue
        with open(out_path, "w") as f:
            f.write(header)
        print(f"gen_config: {source} -> lib/arctos_board/{node}_config.h")


if "Import" in globals():  # running as a PlatformIO extra_script
    Import("env")  # noqa: F821
    generate_all(env["PROJECT_DIR"], env.subst("$PYTHONEXE"))  # noqa: F821
elif __name__ == "__main__":
    generate_all(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
