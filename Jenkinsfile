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
    MINIFORGE_DIR = "${env.WORKSPACE ?: 'workspace'}/miniforge"
    MINIFORGE_BIN = "${env.WORKSPACE ?: 'workspace'}/miniforge/bin"
    // Miniforge installer URL (x86_64 Linux)
    MINIFORGE_URL = "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
  }

  stages {
    stage('Prepare Python (Miniforge) & Tools') {
      steps {
        script {
          sh '''
            set -e
            echo "=== PREP: workspace=${WORKSPACE:-unknown} user=$(whoami 2>/dev/null || true)"

            # If system python3 present, use it (fast path)
            if command -v python3 >/dev/null 2>&1; then
              echo "System python3 found: $(python3 --version)"
              PY_BIN="$(command -v python3)"
            else
              echo "No system python3. Installing Miniforge into workspace: ${MINIFORGE_DIR}"

              mkdir -p "${MINIFORGE_DIR}"
              INSTALLER="${WORKSPACE}/miniforge_installer.sh"
              # download installer (try curl then wget)
              if command -v curl >/dev/null 2>&1; then
                curl -fsSL "${MINIFORGE_URL}" -o "${INSTALLER}" || true
              elif command -v wget >/dev/null 2>&1; then
                wget -qO "${INSTALLER}" "${MINIFORGE_URL}" || true
              fi

              if [ -f "${INSTALLER}" ]; then
                chmod +x "${INSTALLER}"
                echo "Running Miniforge installer (non-interactive)..."
                bash "${INSTALLER}" -b -p "${MINIFORGE_DIR}" || true
                rm -f "${INSTALLER}"
              else
                echo "Miniforge installer download failed; will attempt fallback methods."
              fi

              # If Miniforge installed, set PY_BIN to it
              if [ -x "${MINIFORGE_BIN}/python" ]; then
                PY_BIN="${MINIFORGE_BIN}/python"
                echo "Miniforge python available: $(${PY_BIN} --version)"
              else
                echo "Miniforge not available. Trying fallback options..."
                PY_BIN=""
              fi
            fi

            # Fallback: look for generic "python" that might be python3
            if [ -z "${PY_BIN}" ] && command -v python >/dev/null 2>&1; then
              pyv=$(python -c 'import sys; print(sys.version_info[0])' 2>/dev/null || echo "0")
              if [ "$pyv" = "3" ]; then
                PY_BIN="$(command -v python)"
                echo "Using python from 'python': $(${PY_BIN} --version)"
              fi
            fi

            # Final sanity: fail fast if no python
            if [ -z "${PY_BIN}" ]; then
              echo "ERROR: no usable Python interpreter found or installed."
              echo "Tried system python3, Miniforge at ${MINIFORGE_DIR}, and python."
              exit 2
            fi

            # Ensure pip is available and install requests
            if "${PY_BIN}" -m pip --version >/dev/null 2>&1; then
              echo "pip available for ${PY_BIN}"
            else
              echo "Bootstrapping pip for ${PY_BIN}"
              "${PY_BIN}" -m ensurepip --upgrade || true
              "${PY_BIN}" -m pip install --upgrade pip setuptools wheel || true
            fi

            echo "Installing Python dependency: requests"
            "${PY_BIN}" -m pip install --no-cache-dir requests || true

            # Expose the chosen python binary path into a small file for later stages
            echo "${PY_BIN}" > "${WORKSPACE}/.python_bin_path"
            echo "Python bootstrap complete. PY_BIN=${PY_BIN}"

            # Prepare CF CLI (local workspace fallback)
            if ! command -v cf >/dev/null 2>&1; then
              echo "CF CLI not found. Downloading into ${LOCAL_CF_DIR}"
              mkdir -p "${LOCAL_CF_DIR}"
              TMP_ARCH="${LOCAL_CF_DIR}/cf.tgz"
              if command -v curl >/dev/null 2>&1; then
                curl -fsSL "${CF_INSTALL_URL}" -o "${TMP_ARCH}" || true
              elif command -v wget >/dev/null 2>&1; then
                wget -qO "${TMP_ARCH}" "${CF_INSTALL_URL}" || true
              fi
              if [ -f "${TMP_ARCH}" ]; then
                tar -xzf "${TMP_ARCH}" -C "${LOCAL_CF_DIR}" || true
                chmod +x "${LOCAL_CF_BIN}" || true
                echo "Local cf prepared at ${LOCAL_CF_BIN}"
              else
                echo "Could not download CF CLI; post-cleanup will skip cf logout if needed."
              fi
            else
              echo "System cf available: $(cf --version 2>/dev/null || true)"
            fi
          '''
        }
      }
    }

    stage('Select JSON File Internally') {
      steps {
        script {
          if (params.MODE == 'set') {
            env.CHOSEN_JSON = "set_env_parameter.json"
          } else {
            env.CHOSEN_JSON = "tenant_credentials.json"
          }
          sh """
            if [ ! -f "${env.CHOSEN_JSON}" ]; then
              echo "ERROR: ${env.CHOSEN_JSON} not found in workspace"
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
              # read python binary chosen in prep stage
              PY_BIN="$(cat "${WORKSPACE}/.python_bin_path" 2>/dev/null || true)"
              if [ -z "${PY_BIN}" ]; then
                echo "ERROR: python binary path not set. Aborting."
                exit 2
              fi
              echo "Using python: ${PY_BIN} (${PY_BIN} --version)"
              CMD="${PY_BIN} set_env_parameter.py --mode '${MODE}' --landscape '${LANDSCAPE}' --json-file '${CHOSEN_JSON}'"
              if [ "${MODE}" = "set" ]; then
                CMD="${CMD} --value '${ENV_VARIABLE_VALUE}' --app-name '${APP_NAME}'"
              fi
              if [ "${MODE}" = "read" ] && [ -n "${TENANT}" ]; then
                CMD="${CMD} --tenant '${TENANT}'"
              fi
              echo "Executing: ${CMD}"
              eval ${CMD}
            '''
          }
        }
      }
    }
  }

  post {
    always {
      script {
        sh '''
          set -e || true
          echo "POST: Attempting CF logout (system or workspace-local)"
          if command -v cf >/dev/null 2>&1; then
            cf logout || true
          elif [ -x "${LOCAL_CF_BIN}" ]; then
            "${LOCAL_CF_BIN}" logout || true
          else
            echo "cf not available; skipping logout"
          fi
        '''
      }
    }
  }
}
