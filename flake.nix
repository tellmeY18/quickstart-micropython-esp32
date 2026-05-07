{
  description = "ESP32 MicroPython quickstart toolkit";

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

        # Absolute path to this repository at build time
        repoDir = toString ./.;

        firmware = {
          esp32 = pkgs.fetchurl {
            url = "https://micropython.org/resources/firmware/ESP32_GENERIC-20240602-v1.23.0.bin";
            sha256 = "sha256-XkQhdsfpA0eqECkVB33aWfeVrxkPkH85Ge4eTleYRxY=";
          };
          esp32c3 = pkgs.fetchurl {
            url = "https://micropython.org/resources/firmware/ESP32_GENERIC_C3-20240602-v1.23.0.bin";
            sha256 = "sha256-gFi31utV+BJPvcx5fi6LOa6UehjfY1Vn4CyHhodMBP0=";
          };
          esp32s2 = pkgs.fetchurl {
            url = "https://micropython.org/resources/firmware/ESP32_GENERIC_S2-20240602-v1.23.0.bin";
            sha256 = "sha256-t2ExDdbS4FZ7o0SZTur34UTQdlaim8LymDnpqtM23Yk=";
          };
          esp32s3 = pkgs.fetchurl {
            url = "https://micropython.org/resources/firmware/ESP32_GENERIC_S3-20240602-v1.23.0.bin";
            sha256 = "sha256-uRCAry6beLrUMI+Yu2GHVnyuJO13zX9I75m0evPvBVU=";
          };
        };

        # Meshtastic firmware v2.7.15 (latest stable)
        meshtastic-version = "2.7.15.567b8ea";
        meshtastic-tag = "v2.7.15.567b8ea";

        meshtastic-firmware = {
          esp32 =
            pkgs.runCommand "meshtastic-fw-esp32"
              {
                src = pkgs.fetchurl {
                  url = "https://github.com/meshtastic/firmware/releases/download/${meshtastic-tag}/firmware-esp32-${meshtastic-version}.zip";
                  sha256 = "7ee73fe1f351156a53c99e9b34e25a318271745ef4617540d252d49a75a2598e";
                };
                nativeBuildInputs = [ pkgs.unzip ];
              }
              ''
                mkdir -p $out
                cd $out
                unzip $src
              '';
          esp32c3 =
            pkgs.runCommand "meshtastic-fw-esp32c3"
              {
                src = pkgs.fetchurl {
                  url = "https://github.com/meshtastic/firmware/releases/download/${meshtastic-tag}/firmware-esp32c3-${meshtastic-version}.zip";
                  sha256 = "d7893fdd3149ade63039a430e6530f650bf50d900a1f4578ae663efce8f1671b";
                };
                nativeBuildInputs = [ pkgs.unzip ];
              }
              ''
                mkdir -p $out
                cd $out
                unzip $src
              '';
          esp32c6 =
            pkgs.runCommand "meshtastic-fw-esp32c6"
              {
                src = pkgs.fetchurl {
                  url = "https://github.com/meshtastic/firmware/releases/download/${meshtastic-tag}/firmware-esp32c6-${meshtastic-version}.zip";
                  sha256 = "a1e0daafe70d2bb8f8841f0b9159296618fd9b0273b42d8247efc80a2fec2ae1";
                };
                nativeBuildInputs = [ pkgs.unzip ];
              }
              ''
                mkdir -p $out
                cd $out
                unzip $src
              '';
          esp32s3 =
            pkgs.runCommand "meshtastic-fw-esp32s3"
              {
                src = pkgs.fetchurl {
                  url = "https://github.com/meshtastic/firmware/releases/download/${meshtastic-tag}/firmware-esp32s3-${meshtastic-version}.zip";
                  sha256 = "ac39f8b6517feb7bf6a6d173c46fca808680723e8bc4544edb3185e31398acdc";
                };
                nativeBuildInputs = [ pkgs.unzip ];
              }
              ''
                mkdir -p $out
                cd $out
                unzip $src
              '';
        };

        esp-helper = pkgs.writeShellScriptBin "esp" ''
          set -euo pipefail

          FIRMWARE_ESP32="${firmware.esp32}"
          FIRMWARE_ESP32C3="${firmware.esp32c3}"
          FIRMWARE_ESP32S2="${firmware.esp32s2}"
          FIRMWARE_ESP32S3="${firmware.esp32s3}"
          REPO_DIR="${repoDir}"

          MESHTASTIC_VERSION="${meshtastic-version}"
          MESH_FW_ESP32="${meshtastic-firmware.esp32}"
          MESH_FW_ESP32C3="${meshtastic-firmware.esp32c3}"
          MESH_FW_ESP32C6="${meshtastic-firmware.esp32c6}"
          MESH_FW_ESP32S3="${meshtastic-firmware.esp32s3}"

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

            if echo "$output" | grep -qi "ESP32-S3"; then echo "esp32s3"
            elif echo "$output" | grep -qi "ESP32-S2"; then echo "esp32s2"
            elif echo "$output" | grep -qi "ESP32-C3"; then echo "esp32c3"
            elif echo "$output" | grep -qi "ESP32"; then  echo "esp32"
            else
              echo "ERROR: Unknown chip. Supported: ESP32, ESP32-C3, ESP32-S2, ESP32-S3." >&2
              exit 1
            fi
          }

          firmware_for_chip() {
            case "$1" in
              esp32)   echo "$FIRMWARE_ESP32";;
              esp32c3) echo "$FIRMWARE_ESP32C3";;
              esp32s2) echo "$FIRMWARE_ESP32S2";;
              esp32s3) echo "$FIRMWARE_ESP32S3";;
            esac
          }

          flash_offset_for_chip() {
            case "$1" in
              esp32) echo "0x1000";;
              *)     echo "0x0";;
            esac
          }

          mesh_fw_for_chip() {
            case "$1" in
              esp32)   echo "$MESH_FW_ESP32";;
              esp32c3) echo "$MESH_FW_ESP32C3";;
              esp32c6) echo "$MESH_FW_ESP32C6";;
              esp32s3) echo "$MESH_FW_ESP32S3";;
              *) echo ""; return 1;;
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
            echo "Syncing project files ..."
            local port; port=$(detect_port)

            # Collect all .py and .json files in current directory, excluding nix/git/doc files
            local -a files=()
            for f in *.py *.json; do
              [ ! -f "$f" ] && continue
              case "$f" in
                flake.nix|flake.lock|*.md) continue;;
              esac
              files+=("$f")
            done

            # Collect lib/ directory if it exists
            local -a lib_files=()
            if [ -d "lib" ]; then
              for f in lib/*.py; do
                [ -f "$f" ] && lib_files+=("$f")
              done
            fi

            if [ ''${#files[@]} -eq 0 ] && [ ''${#lib_files[@]} -eq 0 ]; then
              echo "ERROR: No .py or .json files found in current directory." >&2
              echo "  Did you run 'esp init <template>' first?" >&2
              exit 1
            fi

            echo "Files to sync:"
            for f in "''${files[@]}"; do
              echo "  $f"
            done
            for f in "''${lib_files[@]}"; do
              echo "  $f"
            done

            # Create lib/ on device if we have lib files
            if [ ''${#lib_files[@]} -gt 0 ]; then
              mpremote connect "$port" mkdir :lib 2>/dev/null || true
            fi

            # Build the mpremote command chain
            local -a cmd=(mpremote connect "$port")
            local first=1
            for f in "''${files[@]}" "''${lib_files[@]}"; do
              [ "$first" = 1 ] && first=0 || cmd+=(+)
              cmd+=(cp "$f" :"$f")
            done
            cmd+=(+ reset)
            "''${cmd[@]}"
            echo "Done. Board reset."
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

          # ---------- meshtastic commands ----------
          cmd_mesh_boards() {
            local port; port=$(detect_port)
            local chip; chip=$(detect_chip "$port")
            local fw_dir; fw_dir=$(mesh_fw_for_chip "$chip")
            if [ -z "$fw_dir" ]; then
              echo "ERROR: No Meshtastic firmware available for chip '$chip'." >&2
              exit 1
            fi
            echo "Available Meshtastic boards for $chip (v$MESHTASTIC_VERSION):"
            echo ""
            for f in "$fw_dir"/firmware-*-"''${MESHTASTIC_VERSION}".bin; do
              [ -f "$f" ] || continue
              local base; base=$(basename "$f")
              local board; board=$(echo "$base" | sed "s/^firmware-//;s/-''${MESHTASTIC_VERSION}\.bin$//")
              echo "  $board"
            done
          }

          cmd_mesh_flash() {
            local board="''${1:-}"
            if [ -z "$board" ]; then
              echo "Usage: esp mesh flash <board>" >&2
              echo "" >&2
              echo "Run 'esp mesh boards' to see available boards." >&2
              exit 1
            fi

            local port; port=$(detect_port)
            local chip; chip=$(detect_chip "$port")
            local fw_dir; fw_dir=$(mesh_fw_for_chip "$chip")
            if [ -z "$fw_dir" ]; then
              echo "ERROR: No Meshtastic firmware available for chip '$chip'." >&2
              exit 1
            fi

            # Find the factory binary
            local factory_bin="$fw_dir/firmware-''${board}-''${MESHTASTIC_VERSION}.bin"
            if [ ! -f "$factory_bin" ]; then
              echo "ERROR: No firmware found for board '$board' on chip '$chip'." >&2
              echo "" >&2
              echo "Available boards for $chip:" >&2
              for f in "$fw_dir"/firmware-*-"''${MESHTASTIC_VERSION}".bin; do
                [ -f "$f" ] || continue
                local b; b=$(basename "$f" | sed "s/^firmware-//;s/-''${MESHTASTIC_VERSION}\.bin$//")
                echo "  $b" >&2
              done
              exit 1
            fi

            # Find metadata JSON
            local meta_json="$fw_dir/firmware-''${board}-''${MESHTASTIC_VERSION}.mt.json"
            local ota_offset="0x260000"
            local spiffs_offset="0x300000"
            local mcu="$chip"

            if [ -f "$meta_json" ]; then
              ota_offset=$(jq -r '.part[] | select(.subtype == "ota_1") | .offset' "$meta_json" 2>/dev/null || echo "0x260000")
              spiffs_offset=$(jq -r '.part[] | select(.subtype == "spiffs") | .offset' "$meta_json" 2>/dev/null || echo "0x300000")
              mcu=$(jq -r '.mcu // empty' "$meta_json" 2>/dev/null || echo "$chip")
            fi

            # Find OTA binary
            local ota_bin="$fw_dir/bleota.bin"

            # Find LittleFS binary
            local littlefs_bin="$fw_dir/littlefs-''${board}-''${MESHTASTIC_VERSION}.bin"

            echo ""
            echo "  WARNING: Do NOT power on a Meshtastic device without an antenna attached!"
            echo ""
            echo "  Flashing Meshtastic firmware for board: $board"
            echo "  Chip: $chip | Firmware: v$MESHTASTIC_VERSION"
            echo ""
            echo "  Factory:  $(basename "$factory_bin")"
            [ -f "$ota_bin" ] && echo "  OTA:      $(basename "$ota_bin") @ $ota_offset"
            [ -f "$littlefs_bin" ] && echo "  LittleFS: $(basename "$littlefs_bin") @ $spiffs_offset"
            echo ""
            echo "  This will ERASE all existing firmware (MicroPython or otherwise)."
            echo ""

            # Step 1: Erase
            echo "Step 1/4: Erasing flash..."
            esptool --port "$port" erase_flash

            # Step 2: Write factory firmware
            echo "Step 2/4: Writing factory firmware..."
            esptool --port "$port" --baud 460800 write_flash 0x00 "$factory_bin"

            # Step 3: Write OTA (if available)
            if [ -f "$ota_bin" ]; then
              echo "Step 3/4: Writing OTA partition..."
              esptool --port "$port" --baud 460800 write_flash "$ota_offset" "$ota_bin"
            else
              echo "Step 3/4: Skipping OTA (not found)"
            fi

            # Step 4: Write LittleFS (if available)
            if [ -f "$littlefs_bin" ]; then
              echo "Step 4/4: Writing LittleFS..."
              esptool --port "$port" --baud 460800 write_flash "$spiffs_offset" "$littlefs_bin"
            else
              echo "Step 4/4: Skipping LittleFS (not found)"
            fi

            echo ""
            echo "=== Meshtastic firmware flashed successfully ==="
            echo ""
            echo "Next steps:"
            echo "  1. Attach antenna before powering on!"
            echo "  2. Configure via Meshtastic app (BLE) or:"
            echo "     esp mesh config --info"
            echo "  3. Set your region: esp mesh config --set lora.region US"
          }

          cmd_mesh_info() {
            echo "Meshtastic firmware: v$MESHTASTIC_VERSION"
            echo ""
            echo "Pinned architectures:"
            echo "  esp32    $MESH_FW_ESP32"
            echo "  esp32c3  $MESH_FW_ESP32C3"
            echo "  esp32c6  $MESH_FW_ESP32C6"
            echo "  esp32s3  $MESH_FW_ESP32S3"
            echo ""
            echo "Run 'esp mesh boards' to list available boards for your connected device."
          }

          cmd_mesh_config() {
            if ! command -v meshtastic &>/dev/null; then
              echo "ERROR: 'meshtastic' CLI not found." >&2
              echo "  Install it with: pip install meshtastic" >&2
              exit 1
            fi
            local port; port=$(detect_port)
            if [ $# -eq 0 ]; then
              echo "Usage: esp mesh config [meshtastic CLI args...]" >&2
              echo "" >&2
              echo "Examples:" >&2
              echo "  esp mesh config --info" >&2
              echo "  esp mesh config --set lora.region US" >&2
              echo "  esp mesh config --get" >&2
              exit 1
            fi
            meshtastic --port "$port" "$@"
          }

          # ---------- template commands ----------
          cmd_templates() {
            echo "Available templates:"
            echo "  minimal     WiFi + health-check endpoint only"
            echo "  gpio        Digital GPIO control over HTTP"
            echo "  sensors     ADC + I2C + internal temperature"
            echo "  pwm         PWM output control"
            echo "  neopixel    WS2812B RGB LED control"
            echo "  full        Everything combined (batteries-included)"
            echo ""
            echo "Usage: esp init <template>"
          }

          cmd_init() {
            local template="''${1:-}"
            if [ -z "$template" ]; then
              echo "Usage: esp init <template>" >&2
              echo "" >&2
              cmd_templates >&2
              exit 1
            fi

            local template_dir="$REPO_DIR/templates/$template"
            local core_dir="$REPO_DIR/core"

            if [ ! -d "$template_dir" ]; then
              echo "ERROR: Unknown template '$template'." >&2
              echo "" >&2
              echo "Available templates:" >&2
              for d in "$REPO_DIR"/templates/*/; do
                [ -d "$d" ] && echo "  $(basename "$d")" >&2
              done
              exit 1
            fi

            echo "Initializing from template: $template"
            echo ""

            # --- Copy core files ---
            echo "Copying core files..."

            # boot.py
            if [ -f "$core_dir/boot.py" ]; then
              cp "$core_dir/boot.py" ./boot.py
              echo "  boot.py"
            fi

            # debuglog.py (from core if it exists, otherwise from template)
            if [ -f "$core_dir/debuglog.py" ]; then
              cp "$core_dir/debuglog.py" ./debuglog.py
              echo "  debuglog.py"
            elif [ -f "$template_dir/debuglog.py" ]; then
              cp "$template_dir/debuglog.py" ./debuglog.py
              echo "  debuglog.py (from template)"
            fi

            # lib/ directory
            if [ -d "$core_dir/lib" ]; then
              mkdir -p ./lib
              for f in "$core_dir"/lib/*.py; do
                if [ -f "$f" ]; then
                  cp "$f" "./lib/$(basename "$f")"
                  echo "  lib/$(basename "$f")"
                fi
              done
            fi

            # --- Copy template files ---
            echo ""
            echo "Copying template files..."

            for f in "$template_dir"/*.py; do
              if [ -f "$f" ]; then
                local base; base=$(basename "$f")
                # Skip debuglog.py if already copied from core
                if [ "$base" = "debuglog.py" ] && [ -f ./debuglog.py ]; then
                  continue
                fi
                cp "$f" "./$base"
                echo "  $base"
              fi
            done

            # --- Copy config.json.example (always) ---
            if [ -f "$template_dir/config.json.example" ]; then
              cp "$template_dir/config.json.example" ./config.json.example
              echo "  config.json.example"
            fi

            # --- Copy config.json (only if it doesn't exist) ---
            if [ ! -f ./config.json ]; then
              if [ -f "$template_dir/config.json.example" ]; then
                cp "$template_dir/config.json.example" ./config.json
                echo "  config.json (created from example)"
              fi
            else
              echo "  config.json already exists, skipping"
            fi

            echo ""
            echo "=== Template '$template' initialized ==="
            echo ""
            echo "Next steps:"
            echo "  1. Edit config.json with your WiFi credentials"
            echo "  2. Run 'esp sync' to push files to the board"
          }

          # ---------- deprecation wrapper ----------
          deprecation_notice() {
            local cmd="$1"
            local example="$2"
            local doc="$3"
            echo "" >&2
            echo "NOTE: 'esp $cmd' is deprecated. Use curl directly:" >&2
            echo "  $example" >&2
            echo "  See $doc for examples." >&2
            echo "" >&2
          }

          # ---------- main dispatch ----------
          case "''${1:-}" in
            detect)    cmd_detect;;
            erase)     cmd_erase;;
            flash)     cmd_flash;;
            monitor)   cmd_monitor;;
            repl)      cmd_repl;;
            sync)      cmd_sync;;
            push)      shift; cmd_push "$@";;
            run)       shift; cmd_run "$@";;
            ls)        shift; cmd_ls "$@";;
            log)       shift; cmd_log "$@";;
            init)      shift; cmd_init "$@";;
            templates) cmd_templates;;
            gpio)
              shift
              deprecation_notice "gpio" \
                "curl -s http://\$ESP_IP/api/gpio/8 | jq" \
                "templates/gpio/README.md"
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
              deprecation_notice "adc" \
                "curl -s http://\$ESP_IP/api/adc/34 | jq" \
                "templates/sensors/README.md"
              require_ip
              [ -z "''${1:-}" ] && { echo "Usage: esp adc <pin>" >&2; exit 1; }
              curl -s "http://$ESP_IP/api/adc/$1" | jq
              ;;
            i2c)
              shift
              deprecation_notice "i2c" \
                "curl -s http://\$ESP_IP/api/i2c/scan | jq" \
                "templates/sensors/README.md"
              require_ip
              case "''${1:-}" in
                scan) curl -s "http://$ESP_IP/api/i2c/scan" | jq;;
                *) echo "Usage: esp i2c {scan}" >&2;;
              esac
              ;;
            stream)
              shift
              deprecation_notice "stream" \
                "websocat ws://\$ESP_IP/ws/stream" \
                "templates/full/README.md"
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
            mesh)
              shift
              case "''${1:-}" in
                boards)  cmd_mesh_boards;;
                flash)   shift; cmd_mesh_flash "$@";;
                info)    cmd_mesh_info;;
                config)  shift; cmd_mesh_config "$@";;
                *) echo "Usage: esp mesh {boards|flash|info|config}" >&2;;
              esac
              ;;
            *) echo "Usage: esp {detect|erase|flash|monitor|repl|sync|push|run|ls|log|init|templates|mesh}";;
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
            echo ""
            echo "  ESP32 MicroPython quickstart toolkit"
            echo "  ------------------------------------"
            echo "  esp detect      Verify board connection"
            echo "  esp templates   List available project templates"
            echo "  esp init <tpl>  Scaffold a project from a template"
            echo "  esp sync        Push project files to the board"
            echo "  esp repl        Open MicroPython REPL"
            echo "  esp mesh        Meshtastic firmware commands"
            echo ""
            echo "  Run 'esp' for all commands."
            echo ""
          '';
        };
      }
    );
}
