pipeline {
  agent any

  parameters {
    choice(name: 'LANDSCAPE', choices: ['eu12','eu21','us31','eu12-fun','eu01-canary'], description: "Select landscape")
    choice(name: 'MODE', choices: ['set','read'], description: "set = update env parameter; read = get token usage")
    string(name: 'ENV_VARIABLE_VALUE', defaultValue: '', description: "Required when MODE=set.")
    string(name: 'TENANT', defaultValue: '', description: "Provide tenant value for read mode")
  }

  environment {
    APP_NAME = 'it-design-service'
    CF_INSTALL_URL = 'https://packages.cloudfoundry.org/stable?release=linux64-binary&source=github'
    LOCAL_CF_DIR = "${env.WORKSPACE ?: 'workspace'}/cfcli"
    LOCAL_CF_BIN = "${env.WORKSPACE ?: 'workspace'}/cfcli/cf"
    MINIFORGE_DIR = "${env.WORKSPACE ?: 'workspace'}/miniforge"
    MINIFORGE_BIN = "${env.WORKSPACE ?: 'workspace'}/miniforge/bin"
    MINIFORGE_URL = "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
  }

  stages {
    stage('Bootstrap Python (robust Miniforge)') {
      steps {
        script {
          sh '''
            set -euo pipefail
            echo "=== Bootstrap Python: workspace=${WORKSPACE:-unknown} user=$(whoami 2>/dev/null || true)"

            # fast path: if system python3 present, use it
            if command -v python3 >/dev/null 2>&1; then
              echo "System python3 found: $(python3 --version)"
              PY_BIN="$(command -v python3)"
            else
              # check if previous miniforge appears valid
              VALID_MINIFORGE=0
              if [ -x "${MINIFORGE_BIN}/python" ]; then
                echo "Found miniforge python at ${MINIFORGE_BIN}/python"
                if "${MINIFORGE_BIN}/python" -c "import sys, json; print({'v':sys.version_info[0]})" >/dev/null 2>&1; then
                  VALID_MINIFORGE=1
                  PY_BIN="${MINIFORGE_BIN}/python"
                else
                  echo "Existing miniforge python exists but failed a quick import test"
                fi
              fi

              # If invalid or missing, attempt a clean install (retry a few times)
              if [ "${VALID_MINIFORGE}" -ne 1 ]; then
                echo "Miniforge not valid or missing. Will reinstall into ${MINIFORGE_DIR}"

                # If dir exists but broken, remove it (safe: workspace owned by jenkins user)
                if [ -d "${MINIFORGE_DIR}" ]; then
                  echo "Removing existing MINIFORGE_DIR (${MINIFORGE_DIR}) to ensure clean install"
                  rm -rf "${MINIFORGE_DIR}" || true
                fi

                mkdir -p "${MINIFORGE_DIR}"
                INSTALLER="${WORKSPACE}/miniforge_installer.sh"

                ATTEMPTS=0
                MAX_ATTEMPTS=3
                SUCCESS=0
                while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
                  ATTEMPTS=$((ATTEMPTS+1))
                  echo "Install attempt ${ATTEMPTS}/${MAX_ATTEMPTS}..."
                  # download installer
                  if command -v curl >/dev/null 2>&1; then
                    curl -fsSL "${MINIFORGE_URL}" -o "${INSTALLER}" || true
                  elif command -v wget >/dev/null 2>&1; then
                    wget -qO "${INSTALLER}" "${MINIFORGE_URL}" || true
                  else
                    echo "No curl/wget available to download miniforge installer"
                  fi

                  if [ -f "${INSTALLER}" ]; then
                    chmod +x "${INSTALLER}" || true
                    # use -b -p for silent install; if installer complains about directory existing, we removed it above
                    bash "${INSTALLER}" -b -p "${MINIFORGE_DIR}" || true
                    rm -f "${INSTALLER}" || true
                  else
                    echo "Installer not present after download attempt"
                  fi

                  # validate
                  if [ -x "${MINIFORGE_BIN}/python" ]; then
                    if "${MINIFORGE_BIN}/python" -c "import sys" >/dev/null 2>&1; then
                      SUCCESS=1
                      break
                    fi
                  fi

                  echo "Install attempt ${ATTEMPTS} failed; retrying after short sleep"
                  sleep 3
                  rm -rf "${MINIFORGE_DIR}" || true
                  mkdir -p "${MINIFORGE_DIR}"
                done

                if [ $SUCCESS -eq 1 ]; then
                  echo "Miniforge installed and validated at ${MINIFORGE_BIN}/python"
                  PY_BIN="${MINIFORGE_BIN}/python"
                else
                  echo "Miniforge install failed after ${MAX_ATTEMPTS} attempts"
                  PY_BIN=""
                fi
              fi
            fi

            # fallback: attempt 'python' if it's actually python3
            if [ -z "${PY_BIN:-}" ] && command -v python >/dev/null 2>&1; then
              pyv=$(python -c 'import sys; print(sys.version_info[0])' 2>/dev/null || echo "0")
              if [ "$pyv" = "3" ]; then
                PY_BIN="$(command -v python)"
                echo "Using 'python' as Python3: ${PY_BIN}"
              fi
            fi

            if [ -z "${PY_BIN:-}" ]; then
              echo "ERROR: No usable Python found. Bootstrap failed."
              exit 2
            fi

            # ensure pip and packages
            echo "Ensuring pip for ${PY_BIN}"
            "${PY_BIN}" -m pip --version >/dev/null 2>&1 || { "${PY_BIN}" -m ensurepip --upgrade || true; "${PY_BIN}" -m pip install --upgrade pip setuptools wheel || true; }
            echo "Installing requests"
            "${PY_BIN}" -m pip install --no-cache-dir requests || true

            echo "${PY_BIN}" > "${WORKSPACE}/.python_bin_path"
            echo "Python ready: ${PY_BIN}"
          '''
        }
      }
    }

    stage('Select JSON File') {
      steps {
        script {
          if (params.MODE == 'set') {
            env.CHOSEN_JSON = "set_env_parameter.json"
          } else {
            env.CHOSEN_JSON = "tenant_credentials.json"
          }
          sh """
            if [ ! -f "${env.CHOSEN_JSON}" ]; then
              echo "ERROR: ${env.CHOSEN_JSON} not found"
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
              PY_BIN="$(cat "${WORKSPACE}/.python_bin_path" 2>/dev/null || true)"
              if [ -z "${PY_BIN}" ]; then
                echo "No python binary path set"
                exit 2
              fi
              echo "Using python: ${PY_BIN}"
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
  } // stages

  post {
    always {
      script {
        sh '''
          set -e || true
          echo "POST cleanup: try cf logout (system or local)"
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
