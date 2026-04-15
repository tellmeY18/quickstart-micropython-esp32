{
  description = "ESP32 MicroPython development environment";

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
              echo "ERROR: No serial device found. Is the board plugged in?" >&2
              exit 1
            fi

            if [ ''${#candidates[@]} -gt 1 ]; then
              echo "Multiple devices found, using ''${candidates[0]}" >&2
            fi

            echo "''${candidates[0]}"
          }

          # ---------- require ESP_IP ----------
          require_ip() {
            if [ -z "''${ESP_IP:-}" ]; then
              echo "ERROR: ESP_IP is not set. Export it with the board's IP address." >&2
              echo "  Example: export ESP_IP=192.168.1.42" >&2
              exit 1
            fi
          }

          # ---------- chip detection ----------
          detect_chip() {
            local port="$1"
            echo "Detecting chip on $port ..." >&2
            local output
            output=$(esptool --port "$port" chip_id 2>&1) || {
              echo "ERROR: esptool failed on $port" >&2; exit 1
            }

            if echo "$output" | grep -qi "ESP32-C3"; then echo "esp32c3"
            elif echo "$output" | grep -qi "ESP32"; then  echo "esp32"
            else
              echo "ERROR: Unknown chip. Only ESP32 and ESP32-C3 are supported." >&2
              exit 1
            fi
          }

          firmware_for_chip() {
            case "$1" in
              esp32)   echo "$FIRMWARE_ESP32";;
              esp32c3) echo "$FIRMWARE_ESP32C3";;
            esac
          }

          flash_offset_for_chip() {
            case "$1" in
              esp32) echo "0x1000";;
              *)     echo "0x0";;
            esac
          }

          # ---------- commands ----------
          cmd_detect() {
            local port; port=$(detect_port)
            local chip; chip=$(detect_chip "$port")
            echo "  Port: $port  Chip: $chip"
          }

          cmd_erase() {
            local port; port=$(detect_port)
            esptool --port "$port" erase_flash
          }

          cmd_flash() {
            local port; port=$(detect_port)
            local chip; chip=$(detect_chip "$port")
            local fw;   fw=$(firmware_for_chip "$chip")
            local off;  off=$(flash_offset_for_chip "$chip")
            esptool --port "$port" --baud 460800 write_flash -z "$off" "$fw"
          }

          cmd_monitor() {
            local port; port=$(detect_port)
            picocom -b 115200 "$port"
          }

          cmd_repl() {
            local port; port=$(detect_port)
            mpremote connect "$port" repl
          }

          cmd_push() {
            [ $# -eq 0 ] && { echo "Usage: esp push <file> [...]" >&2; exit 1; }
            local port; port=$(detect_port)
            for f in "$@"; do
              local dir; dir=$(dirname "$f")
              [ "$dir" != "." ] && mpremote connect "$port" mkdir :"$dir" 2>/dev/null || true
              mpremote connect "$port" cp "$f" :"$f"
            done
          }

          cmd_sync() {
            echo "Syncing ..."
            local port; port=$(detect_port)
            local files=(boot.py main.py config.json gpio_api.py debuglog.py lib/microdot.py lib/websocket.py)

            mpremote connect "$port" mkdir :lib 2>/dev/null || true

            local -a cmd=(mpremote connect "$port")
            local first=1
            for f in "''${files[@]}"; do
              if [ -f "$f" ]; then
                [ "$first" = 1 ] && first=0 || cmd+=(+)
                cmd+=(cp "$f" :"$f")
              else
                echo "  SKIP: $f" >&2
              fi
            done
            cmd+=(+ reset)
            "''${cmd[@]}"
            echo "Done."
          }

          cmd_run() {
            [ -z "''${1:-}" ] && { echo "Usage: esp run <script.py>" >&2; exit 1; }
            local port; port=$(detect_port)
            mpremote connect "$port" run "$1"
          }

          cmd_ls() {
            local port; port=$(detect_port)
            mpremote connect "$port" ls :"''${1:-/}"
          }

          cmd_log() {
            local port; port=$(detect_port)
            case "''${1:-}" in
              clear)
                echo "Clearing debug.log on board..."
                mpremote connect "$port" exec "import os; os.remove('debug.log')" 2>/dev/null \
                  && echo "Done." \
                  || echo "No debug.log to clear."
                ;;
              *)
                mpremote connect "$port" cat :debug.log 2>/dev/null \
                  || echo "(no debug.log found on board)"
                ;;
            esac
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
            log)     shift; cmd_log "$@";;
            gpio)
              shift
              require_ip
              [ -z "''${1:-}" ] && { echo "Usage: esp gpio <pin> [value]" >&2; exit 1; }
              if [ -z "''${2:-}" ]; then
                curl -s "http://$ESP_IP/api/gpio/$1" | jq
              else
                curl -s -X POST "http://$ESP_IP/api/gpio/$1/value" \
                  -H 'Content-Type: application/json' \
                  -d "{\"value\":$2}" | jq
              fi
              ;;
            adc)
              shift
              require_ip
              [ -z "''${1:-}" ] && { echo "Usage: esp adc <pin>" >&2; exit 1; }
              curl -s "http://$ESP_IP/api/adc/$1" | jq
              ;;
            i2c)
              shift
              require_ip
              case "''${1:-}" in
                scan) curl -s "http://$ESP_IP/api/i2c/scan" | jq;;
                *) echo "Usage: esp i2c {scan}" >&2;;
              esac
              ;;
            stream)
              shift
              require_ip
              if [ -n "''${1:-}" ]; then
                IFS=',' read -ra pins <<< "$1"
                pin_json=$(printf '%s,' "''${pins[@]}" | sed 's/,$//')
                echo "{\"cmd\":\"stream_config\",\"pins\":[$pin_json],\"interval_ms\":100}" | \
                  websocat "ws://$ESP_IP/ws/stream"
              else
                websocat "ws://$ESP_IP/ws/stream"
              fi
              ;;
            *) echo "Usage: esp {detect|erase|flash|monitor|repl|sync|push|run|ls|log|gpio|adc|i2c|stream}";;
          esac
        '';
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            esptool
            python3
            python3Packages.pyserial
            mpremote
            picocom
            curl
            jq
            websocat
            esp-helper
          ];

          shellHook = ''
            echo "ESP32 dev shell ready. Run 'esp' for commands."
          '';
        };
      }
    );
}
