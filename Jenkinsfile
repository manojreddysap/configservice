pipeline {
  agent any

  parameters {
    choice(name: 'LANDSCAPE', choices: ['eu12','eu21','us31','eu12-fun','eu01-canary'], description: "Select landscape")
    choice(name: 'MODE', choices: ['set','read'], description: "set = update env parameter; read = get token usage")
    string(name: 'ENV_VARIABLE_VALUE', defaultValue: '', description: "Required when MODE=set. Provide only when MODE=set")
    string(name: 'TENANT', defaultValue: '', description: "Tenant value for MODE=read. Provide only when MODE=read")
  }

  environment {
    APP_NAME = 'it-design-service'
    CF_INSTALL_URL = 'https://packages.cloudfoundry.org/stable?release=linux64-binary&source=github'
    LOCAL_CF_DIR = "${env.WORKSPACE}/cfcli"
    LOCAL_CF_BIN = "${env.WORKSPACE}/cfcli/cf"

    MINIFORGE_DIR = "${env.WORKSPACE}/miniforge"
    MINIFORGE_BIN = "${env.WORKSPACE}/miniforge/bin"
    MINIFORGE_URL = "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
  }

  stages {

    stage('Validate Parameters') {
      steps {
        script {
          // Enforce mutual-exclusion and MODE requirements early
          if (params.ENV_VARIABLE_VALUE?.trim() && params.TENANT?.trim()) {
            error("Invalid parameters: provide only one of ENV_VARIABLE_VALUE or TENANT — not both.")
          }
          if (params.MODE == 'set' && !params.ENV_VARIABLE_VALUE?.trim()) {
            error("MODE=set requires ENV_VARIABLE_VALUE (cannot be empty).")
          }
          // MODE=read may omit TENANT (optional); that's allowed
          echo "Parameter validation passed. MODE=${params.MODE}"
        }
      }
    }

    stage('Bootstrap Python (Robust Miniforge)') {
      steps {
        script {
          sh '''
            set -euo pipefail
            echo "=== BOOTSTRAP PYTHON START ==="
            echo "Workspace: ${WORKSPACE}, User: $(whoami)"

            PY_BIN=""

            if command -v python3 >/dev/null 2>&1; then
              PY_BIN="$(command -v python3)"
              echo "System python3 detected: $(${PY_BIN} --version)"
            else
              VALID_MINIFORGE=0
              if [ -x "${MINIFORGE_BIN}/python" ]; then
                echo "Existing Miniforge python detected"
                if "${MINIFORGE_BIN}/python" -c "import sys" >/dev/null 2>&1; then
                  VALID_MINIFORGE=1
                  PY_BIN="${MINIFORGE_BIN}/python"
                fi
              fi

              if [ "${VALID_MINIFORGE}" -ne 1 ]; then
                echo "Miniforge missing or invalid. Reinstalling at ${MINIFORGE_DIR}"
                rm -rf "${MINIFORGE_DIR}" || true

                INSTALLER="${WORKSPACE}/miniforge_installer.sh"
                ATTEMPTS=0
                MAX_ATTEMPTS=3
                SUCCESS=0

                while [ ${ATTEMPTS} -lt ${MAX_ATTEMPTS} ]; do
                  ATTEMPTS=$((ATTEMPTS+1))
                  echo "Miniforge install attempt ${ATTEMPTS}/${MAX_ATTEMPTS}"

                  if command -v curl >/dev/null 2>&1; then
                    curl -fsSL "${MINIFORGE_URL}" -o "${INSTALLER}" || true
                  elif command -v wget >/dev/null 2>&1; then
                    wget -qO "${INSTALLER}" "${MINIFORGE_URL}" || true
                  fi

                  if [ -f "${INSTALLER}" ]; then
                    chmod +x "${INSTALLER}"

                    # Do NOT pre-create MINIFORGE_DIR — installer will create it.
                    bash "${INSTALLER}" -b -p "${MINIFORGE_DIR}" > /tmp/miniforge_install_${ATTEMPTS}.log 2>&1 || true

                    # If installer reported existing dir, attempt update mode as fallback
                    if grep -q "already exists" /tmp/miniforge_install_${ATTEMPTS}.log 2>/dev/null; then
                      echo "Installer reported existing dir. Trying update mode."
                      bash "${INSTALLER}" -u -p "${MINIFORGE_DIR}" > /tmp/miniforge_update_${ATTEMPTS}.log 2>&1 || true
                    fi

                    rm -f "${INSTALLER}" || true
                  fi

                  if [ -x "${MINIFORGE_BIN}/python" ] && "${MINIFORGE_BIN}/python" -c "import sys" >/dev/null 2>&1; then
                    echo "Miniforge installed and validated"
                    SUCCESS=1
                    PY_BIN="${MINIFORGE_BIN}/python"
                    break
                  fi

                  echo "Install attempt ${ATTEMPTS} failed. Cleaning and retrying..."
                  rm -rf "${MINIFORGE_DIR}" || true
                  sleep 3
                done

                if [ ${SUCCESS} -ne 1 ]; then
                  echo "ERROR: Miniforge install failed after ${MAX_ATTEMPTS} attempts"
                  PY_BIN=""
                fi
              fi
            fi

            if [ -z "${PY_BIN}" ] && command -v python >/dev/null 2>&1; then
              PY_BIN="$(command -v python)"
              echo "Using fallback python: $(${PY_BIN} --version)"
            fi

            if [ -z "${PY_BIN}" ]; then
              echo "FATAL: No usable Python interpreter found."
              exit 2
            fi

            echo "Ensuring pip for ${PY_BIN}"
            "${PY_BIN}" -m pip --version >/dev/null 2>&1 || {
              "${PY_BIN}" -m ensurepip --upgrade || true
              "${PY_BIN}" -m pip install --upgrade pip setuptools wheel || true
            }

            echo "Installing requests"
            "${PY_BIN}" -m pip install --no-cache-dir requests || true

            echo "${PY_BIN}" > "${WORKSPACE}/.python_bin_path"
            echo "Python Bootstrap Complete: ${PY_BIN}"
            echo "=== BOOTSTRAP PYTHON END ==="
          '''
        }
      }
    }

    stage('Select JSON File') {
      steps {
        script {
          // Choose internal JSON file depending on MODE
          env.CHOSEN_JSON = (params.MODE == 'set') ? 'set_env_parameter.json' : 'tenant_credentials.json'
          sh """
            if [ ! -f "${CHOSEN_JSON}" ]; then
              echo "ERROR: JSON file ${CHOSEN_JSON} not found in workspace: ${WORKSPACE}"
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
              PY_BIN="$(cat "${WORKSPACE}/.python_bin_path")"
              echo "Running with python: ${PY_BIN}"

              CMD="${PY_BIN} set_env_parameter.py --mode '${MODE}' --landscape '${LANDSCAPE}' --json-file '${CHOSEN_JSON}'"

              # Add mutually exclusive parameters: pass only value or tenant per validation earlier
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
  } // stages

  post {
    always {
      script {
        sh '''
          echo "Post Cleanup: logging out from CF if available"
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
