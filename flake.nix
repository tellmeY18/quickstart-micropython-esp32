{
  description = "ESP32 MicroPython development environment with auto-detection";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      nixpkgs,
      flake-utils,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };

        firmware = {
          esp32 = pkgs.fetchurl {
            url = "https://micropython.org/resources/firmware/ESP32_GENERIC-20240602-v1.23.0.bin";
            sha256 = "sha256-XkQhdsfpA0eqECkVB33aWfeVrxkPkH85Ge4eTleYRxY=";
          };
          esp32c3 = pkgs.fetchurl {
            url = "https://micropython.org/resources/firmware/ESP32_GENERIC_C3-20240602-v1.23.0.bin";
            sha256 = "sha256-gFi31utV+BJPvcx5fi6LOa6UehjfY1Vn4CyHhodMBP0=";
          };
        };

        esp-helper = pkgs.writeShellScriptBin "esp" ''
          set -euo pipefail

          FIRMWARE_ESP32="${firmware.esp32}"
          FIRMWARE_ESP32C3="${firmware.esp32c3}"

          # ---------- port detection ----------
          detect_port() {
            if [ -n "''${ESP_PORT:-}" ]; then
              if [ ! -e "$ESP_PORT" ]; then
                echo "ERROR: ESP_PORT=$ESP_PORT does not exist." >&2
                exit 1
              fi
              echo "$ESP_PORT"
              return
            fi

            local candidates=()
            for p in /dev/cu.usbmodem* /dev/cu.usbserial*; do
              [ -e "$p" ] && candidates+=("$p")
            done
            for p in /dev/ttyUSB* /dev/ttyACM*; do
              [ -e "$p" ] && candidates+=("$p")
            done

            if [ ''${#candidates[@]} -eq 0 ]; then
              echo "ERROR: No serial device found." >&2
              echo "  Checked: /dev/cu.usbmodem* /dev/cu.usbserial* /dev/ttyUSB* /dev/ttyACM*" >&2
              echo "  Make sure your board is plugged in." >&2
              echo "  Or set ESP_PORT manually:  export ESP_PORT=/dev/..." >&2
              exit 1
            fi

            if [ ''${#candidates[@]} -gt 1 ]; then
              echo "Multiple serial devices found:" >&2
              for c in "''${candidates[@]}"; do echo "  - $c" >&2; done
              echo "Using: ''${candidates[0]}" >&2
              echo "  Override with: export ESP_PORT=/dev/..." >&2
            fi

            echo "''${candidates[0]}"
          }

          # ---------- chip detection ----------
          detect_chip() {
            local port="$1"
            echo "Detecting chip on $port ..." >&2
            local output
            output=$(esptool --port "$port" chip_id 2>&1) || {
              echo "ERROR: esptool failed to communicate with device on $port" >&2
              echo "$output" >&2
              exit 1
            }

            if echo "$output" | grep -qi "ESP32-C3"; then   echo "esp32c3"
            elif echo "$output" | grep -qi "ESP32-S3"; then echo "esp32s3"
            elif echo "$output" | grep -qi "ESP32-S2"; then echo "esp32s2"
            elif echo "$output" | grep -qi "ESP32-C6"; then echo "esp32c6"
            elif echo "$output" | grep -qi "ESP32"; then    echo "esp32"
            else
              echo "ERROR: Could not identify chip from esptool output:" >&2
              echo "$output" >&2
              exit 1
            fi
          }

          # ---------- chip -> firmware + offset ----------
          firmware_for_chip() {
            case "$1" in
              esp32)   echo "$FIRMWARE_ESP32";;
              esp32c3) echo "$FIRMWARE_ESP32C3";;
              *)
                echo "ERROR: No firmware bundled for chip '$1'." >&2
                echo "  Supported chips: esp32, esp32c3" >&2
                echo "  Add firmware to flake.nix to support this chip." >&2
                exit 1;;
            esac
          }

          flash_offset_for_chip() {
            case "$1" in
              esp32) echo "0x1000";;
              *)     echo "0x0";;
            esac
          }

          # ---------- mpremote wrapper (port-aware) ----------
          mpr() {
            local port
            port=$(detect_port)
            mpremote connect "$port" "$@"
          }

          # ---------- commands ----------
          cmd_detect() {
            local port; port=$(detect_port)
            local chip; chip=$(detect_chip "$port")
            echo ""
            echo "  Port  : $port"
            echo "  Chip  : $chip"
            echo "  Flash : $(firmware_for_chip "$chip")"
            echo "  Offset: $(flash_offset_for_chip "$chip")"
            echo ""
          }

          cmd_erase() {
            local port; port=$(detect_port)
            local chip; chip=$(detect_chip "$port")
            echo "Erasing flash on $chip @ $port ..."
            esptool --port "$port" erase_flash
          }

          cmd_flash() {
            local port; port=$(detect_port)
            local chip; chip=$(detect_chip "$port")
            local fw;   fw=$(firmware_for_chip "$chip")
            local off;  off=$(flash_offset_for_chip "$chip")
            echo "Flashing $chip @ $port (offset $off) ..."
            echo "  Firmware: $fw"
            esptool --port "$port" --baud 460800 write_flash -z "$off" "$fw"
          }

          cmd_monitor() {
            local port; port=$(detect_port)
            echo "Connecting to REPL on $port (115200 baud) ..."
            echo "  Exit: Ctrl+A then Ctrl+X"
            picocom -b 115200 "$port"
          }

          cmd_repl() {
            # Interactive MicroPython REPL via mpremote (Ctrl+X to exit)
            local port; port=$(detect_port)
            echo "Opening MicroPython REPL on $port ..."
            echo "  Exit: Ctrl+X"
            mpremote connect "$port" repl
          }

          cmd_push() {
            # esp push [file ...]  — copy one or more local files to device,
            # preserving path structure (e.g. modules/foo.py → :modules/foo.py)
            if [ $# -eq 0 ]; then
              echo "Usage: esp push <file> [file ...]" >&2
              exit 1
            fi
            local port; port=$(detect_port)
            for f in "$@"; do
              echo "  → $f"
              # Ensure parent directory exists on device (ignore error if already there)
              local dir
              dir=$(dirname "$f")
              if [ "$dir" != "." ]; then
                mpremote connect "$port" mkdir :"$dir" 2>/dev/null || true
              fi
              mpremote connect "$port" cp "$f" :"$f"
            done
          }

          cmd_sync() {
            # esp sync  — push all project source files in a SINGLE mpremote
            # session using '+' chaining so the board never reboots mid-transfer.
            echo "Syncing project files to device ..."
            local port; port=$(detect_port)

            local files=(
              boot.py
              main.py
              config.json
              lib/microdot.py
            )

            # Build the chained mpremote command as an array.
            # Start by creating the lib directory (ignore error if it exists).
            local -a cmd=(mpremote connect "$port" mkdir :lib)

            for f in "''${files[@]}"; do
              if [ -f "$f" ]; then
                echo "  → $f"
                cmd+=(+ cp "$f" :"$f")
              else
                echo "  SKIP (not found): $f" >&2
              fi
            done

            # Append a reset so the board boots fresh after the transfer.
            cmd+=(+ reset)

            # Execute the whole chain in one connection — no mid-sync reboots.
            "''${cmd[@]}"

            echo ""
            echo "Sync complete."
          }

          cmd_run() {
            # esp run <script.py>  — execute a local script without copying it
            if [ -z "''${1:-}" ]; then
              echo "Usage: esp run <script.py>" >&2
              exit 1
            fi
            local port; port=$(detect_port)
            echo "Running $1 on device ..."
            mpremote connect "$port" run "$1"
          }

          cmd_ls() {
            # esp ls [path]  — list files on device flash
            local port; port=$(detect_port)
            local path="''${1:-/}"
            mpremote connect "$port" ls :"$path"
          }

          # ---------- main ----------
          usage() {
            echo "Usage: esp <command> [args]"
            echo ""
            echo "Hardware:"
            echo "  detect        Auto-detect port, chip, firmware info"
            echo "  erase         Erase flash (run before first flash)"
            echo "  flash         Flash MicroPython firmware"
            echo ""
            echo "Serial:"
            echo "  monitor       picocom REPL (raw serial, 115200 baud)"
            echo "  repl          mpremote REPL (friendlier, Ctrl+X to exit)"
            echo ""
            echo "File transfer:"
            echo "  sync          Push all project files and reset device"
            echo "  push <files>  Push specific file(s) and preserve path"
            echo "  run <file>    Run a local .py without copying it"
            echo "  ls [path]     List files on device flash"
            echo ""
            echo "Environment:"
            echo "  ESP_PORT      Override auto-detected serial port"
            echo ""
          }

          case "''${1:-}" in
            detect)  cmd_detect;;
            erase)   cmd_erase;;
            flash)   cmd_flash;;
            monitor) cmd_monitor;;
            repl)    cmd_repl;;
            sync)    cmd_sync;;
            push)    shift; cmd_push "$@";;
            run)     shift; cmd_run "$@";;
            ls)      shift; cmd_ls "$@";;
            *)       usage;;
          esac
        '';
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            esptool
            python3
            python3Packages.pyserial
            mpremote # file transfer + REPL
            picocom # raw serial monitor
            esp-helper # unified `esp` command
          ];

          shellHook = ''
            echo ""
            echo "ESP32 MicroPython Development Environment"
            echo "========================================="
            echo ""
            echo "Hardware:"
            echo "  esp detect        show detected port, chip, firmware"
            echo "  esp erase         erase flash (first time only)"
            echo "  esp flash         flash MicroPython firmware"
            echo ""
            echo "Serial:"
            echo "  esp monitor       raw picocom REPL"
            echo "  esp repl          mpremote REPL (Ctrl+X to exit)"
            echo ""
            echo "File transfer:"
            echo "  esp sync          push all project files + reset"
            echo "  esp push <files>  push specific file(s)"
            echo "  esp run <file>    run script without copying"
            echo "  esp ls [path]     list device flash"
            echo ""
            echo "Override port:  export ESP_PORT=/dev/cu.usbmodem..."
            echo ""
          '';
        };
      }
    );
}
