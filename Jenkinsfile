pipeline {
  agent any

  parameters {
    choice(name: 'LANDSCAPE', choices: ['eu12','eu21','us31','eu12-fun','eu01-canary'], description: "Select landscape")
    choice(name: 'MODE', choices: ['set','read'], description: "set = update env parameter; read = get token usage")
    string(name: 'ENV_VARIABLE_VALUE', defaultValue: '', description: "Required when MODE=set. Example: pass 19 if today's date is 20.")
    string(name: 'TENANT', defaultValue: '', description: "Provide tenant value for read mode")
  }

  environment {
    APP_NAME = 'it-design-service'
    CF_INSTALL_URL = 'https://packages.cloudfoundry.org/stable?release=linux64-binary&source=github'
    // local cf install dir inside workspace
    LOCAL_CF_DIR = "${env.WORKSPACE ?: 'workspace'}/cfcli"
    LOCAL_CF_BIN = "${env.WORKSPACE ?: 'workspace'}/cfcli/cf"
  }

  stages {
    stage('Prepare Environment - Strong Runtime Install') {
      steps {
        script {
          // Display environment for debugging
          sh '''
            set -e
            echo "=== PREP: workspace=${WORKSPACE:-unknown} user=$(whoami 2>/dev/null || true) uid=$(id -u || true)"
          '''

          // Strong install logic for python3/pip and tools
          sh '''
            set -e

            # helper: run with sudo if available, else as-is
            SUDO=''
            if command -v sudo >/dev/null 2>&1; then
              SUDO='sudo'
            fi

            echo "=== DETECT PACKAGE MANAGER ==="
            PM=""
            if command -v apt-get >/dev/null 2>&1; then
              PM="apt"
            elif command -v yum >/dev/null 2>&1; then
              PM="yum"
            elif command -v dnf >/dev/null 2>&1; then
              PM="dnf"
            elif command -v apk >/dev/null 2>&1; then
              PM="apk"
            else
              PM=""
            fi
            echo "Package manager: ${PM:-none detected}"

            # Try installing python3 & pip using the detected package manager
            if [ -n "${PM}" ]; then
              echo "Attempting to install python3 and pip using package manager (${PM})"
              if [ "${PM}" = "apt" ]; then
                ${SUDO} apt-get update -y || true
                ${SUDO} apt-get install -y --no-install-recommends python3 python3-venv python3-pip wget curl ca-certificates tar unzip || true
              elif [ "${PM}" = "yum" ] || [ "${PM}" = "dnf" ]; then
                ${SUDO} ${PM} install -y python3 python3-pip wget curl ca-certificates tar unzip || true
              elif [ "${PM}" = "apk" ]; then
                ${SUDO} apk add --no-cache python3 py3-pip wget curl ca-certificates tar unzip || true
              fi
            else
              echo "No package manager detected (or not allowed). Will attempt pip bootstrap or ensurepip."
            fi

            # If python3 still missing, check common alternative commands
            if command -v python3 >/dev/null 2>&1; then
              echo "python3 now available: $(python3 --version)"
            else
              echo "python3 not found after package manager attempt. Trying to find 'python' executable."
              if command -v python >/dev/null 2>&1; then
                # on some minimal systems 'python' is python3
                pyv=$(python -c 'import sys; print(sys.version_info[0])' 2>/dev/null || echo "0")
                if [ "$pyv" = "3" ]; then
                  echo "python points to Python3"
                  ln -s "$(command -v python)" /tmp/python3bin || true
                  export PATH="/tmp:$PATH"
                fi
              fi
            fi

            # Ensure pip3 exists: try python3 -m ensurepip or get-pip.py
            if command -v python3 >/dev/null 2>&1; then
              if command -v pip3 >/dev/null 2>&1; then
                echo "pip3 present: $(pip3 --version)"
              else
                echo "pip3 missing; attempting ensurepip"
                python3 -m ensurepip --upgrade || true
                python3 -m pip install --upgrade pip setuptools wheel || true
                if command -v pip3 >/dev/null 2>&1; then
                  echo "pip3 installed: $(pip3 --version)"
                else
                  echo "ensurepip didn't install pip3; attempting get-pip.py"
                  TMPGET="$(mktemp -d)"
                  if command -v curl >/dev/null 2>&1; then
                    curl -sS https://bootstrap.pypa.io/get-pip.py -o "${TMPGET}/get-pip.py" || true
                  elif command -v wget >/dev/null 2>&1; then
                    wget -q -O "${TMPGET}/get-pip.py" https://bootstrap.pypa.io/get-pip.py || true
                  fi
                  if [ -f "${TMPGET}/get-pip.py" ]; then
                    python3 "${TMPGET}/get-pip.py" || true
                  fi
                  rm -rf "${TMPGET}" || true
                fi
              fi
            fi

            # As a last resort, if pip3 still not available but python3 is present, use python3 -m pip with --user when possible
            if command -v python3 >/dev/null 2>&1 && ! command -v pip3 >/dev/null 2>&1; then
              echo "pip3 still missing; will use python3 -m pip (user install) when installing packages"
            fi

            # Ensure wget/curl present for downloads
            if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
              echo "Warning: neither curl nor wget detected. Download-dependent steps may fail."
            fi

            echo "=== INSTALL/VERIFY requests python package ==="
            if command -v pip3 >/dev/null 2>&1; then
              pip3 install --no-cache-dir requests || true
            elif command -v python3 >/dev/null 2>&1; then
              python3 -m pip install --user --no-cache-dir requests || true
            else
              echo "Cannot install requests: python3/pip3 unavailable."
            fi

            echo "=== ENSURE CF CLI AVAILABLE (local workspace fallback) ==="
            if command -v cf >/dev/null 2>&1; then
              echo "cf already present: $(cf --version 2>/dev/null || true)"
            else
              echo "Downloading CF CLI into workspace at ${LOCAL_CF_DIR}"
              mkdir -p "${LOCAL_CF_DIR}"
              TMP_ARCH="${LOCAL_CF_DIR}/cf.tgz"
              if command -v curl >/dev/null 2>&1; then
                curl -sSfL "${CF_INSTALL_URL}" -o "${TMP_ARCH}" || true
              elif command -v wget >/dev/null 2>&1; then
                wget -q -O "${TMP_ARCH}" "${CF_INSTALL_URL}" || true
              fi
              if [ -f "${TMP_ARCH}" ]; then
                tar -xzf "${TMP_ARCH}" -C "${LOCAL_CF_DIR}" || true
                chmod +x "${LOCAL_CF_BIN}" || true
                echo "Local cf binary prepared at ${LOCAL_CF_BIN}"
              else
                echo "CF CLI download failed; will skip cf-based steps if cf not available."
              fi
            fi

            echo "=== PREP COMPLETE ==="
            command -v python3 || echo "python3: NOT FOUND"
            command -v pip3 || echo "pip3: NOT FOUND"
            command -v cf || echo "cf: NOT FOUND (local fallback: ${LOCAL_CF_BIN})"
          '''
        }
      }
    } // stage Prepare Environment

    stage('Select JSON File Internally') {
      steps {
        script {
          if (params.MODE == 'set') {
            env.CHOSEN_JSON = "set_env_parameter.json"
          } else {
            env.CHOSEN_JSON = "tenant_credentials.json"
          }

          echo "Using internal JSON file: ${env.CHOSEN_JSON}"

          sh """
            if [ ! -f "${env.CHOSEN_JSON}" ]; then
              echo "ERROR: ${env.CHOSEN_JSON} not found in workspace: ${WORKSPACE}"
              ls -la || true
              exit 1
            fi
          """
        }
      }
    }

    stage('Run Python Script') {
      steps {
        script {
          catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
            sh '''
              set -e
              # Choose python binary
              if command -v python3 >/dev/null 2>&1; then
                PY=python3
              elif command -v python >/dev/null 2>&1; then
                # if python exists, check if it is python3
                pyv=$(python -c 'import sys; print(sys.version_info[0])' 2>/dev/null || echo "0")
                if [ "$pyv" = "3" ]; then
                  PY=python
                else
                  echo "python exists but is not python3"
                  exit 2
                fi
              else
                echo "ERROR: python3 not available. Aborting script run."
                exit 2
              fi

              # Prefer pip3 if present, else use python -m pip
              if command -v pip3 >/dev/null 2>&1; then
                PIP=pip3
              else
                PIP="${PY} -m pip"
              fi

              # Ensure requests is available, attempt install if missing
              ${PY} -c "import requests" >/dev/null 2>&1 || ${PIP} install --no-cache-dir requests || true

              # Build command to invoke Python script
              CMD="${PY} set_env_parameter.py --mode '${MODE}' --landscape '${LANDSCAPE}' --json-file '${CHOSEN_JSON}'"
              if [ "${MODE}" = "set" ]; then
                CMD="${CMD} --value '${ENV_VARIABLE_VALUE}' --app-name '${APP_NAME}'"
              fi
              if [ "${MODE}" = "read" ] && [ -n "${TENANT}" ]; then
                CMD="${CMD} --tenant '${TENANT}'"
              fi

              echo "Executing: ${CMD}"
              eval ${CMD}
            '''
          } // catchError
        }
      }
    }
  } // stages

  post {
    always {
      script {
        // Use system cf if present, else local workspace cf binary if available
        sh '''
          set -e || true
          echo "POST-CLEANUP: attempt to logout CF (system or local)"
          if command -v cf >/dev/null 2>&1; then
            echo "Using system cf"
            cf logout || true
          elif [ -x "${LOCAL_CF_BIN}" ]; then
            echo "Using local cf at ${LOCAL_CF_BIN}"
            "${LOCAL_CF_BIN}" logout || true
          else
            echo "cf not available; skipping logout"
          fi
        '''
      }
    }
  }
}
