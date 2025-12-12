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
    # local cf install dir inside workspace
    LOCAL_CF_DIR = "${env.WORKSPACE ?: 'workspace'}/cfcli"
    LOCAL_CF_BIN = "${env.WORKSPACE ?: 'workspace'}/cfcli/cf"
  }

  stages {

    stage('Prepare Environment') {
      steps {
        script {
          // ensure workspace exists
          sh '''
            set -e
            echo "Workspace: ${WORKSPACE:-unknown}"
            echo "UID: $(id -u)  GID: $(id -g)  USER: $(whoami 2>/dev/null || true)"
          '''

          // Attempt to ensure system has minimal tools: python3, pip3, curl/wget
          sh '''
            set -e
            echo "=== CHECK FOR python3 ==="
            if command -v python3 >/dev/null 2>&1; then
              echo "python3 present: $(python3 --version)"
            else
              echo "python3 not found"
              # try apt-get if available (best-effort)
              if command -v apt-get >/dev/null 2>&1; then
                echo "Attempting apt-get install python3 python3-pip (requires permission)..."
                apt-get update -y || true
                apt-get install -y --no-install-recommends python3 python3-pip || true
              fi
            fi

            echo "=== ENSURE pip3 ==="
            if command -v pip3 >/dev/null 2>&1; then
              echo "pip3 present"
            else
              if command -v python3 >/dev/null 2>&1; then
                echo "Trying python3 -m ensurepip..."
                python3 -m ensurepip --upgrade || true
                python3 -m pip install --upgrade pip || true
              fi
            fi

            echo "=== CHECK FOR curl or wget ==="
            if command -v curl >/dev/null 2>&1; then
              echo "curl present"
            elif command -v wget >/dev/null 2>&1; then
              echo "wget present"
            else
              echo "Warning: neither curl nor wget found. Network downloads will fail."
            fi

            echo "=== CHECK FOR CF CLI ==="
            if command -v cf >/dev/null 2>&1; then
              echo "cf present: $(cf --version 2>/dev/null || true)"
            else
              echo "cf not found; will attempt local download to workspace (no sudo required)"
              mkdir -p "${LOCAL_CF_DIR}"
              TMP_ARCHIVE="${LOCAL_CF_DIR}/cf.tgz"
              if command -v curl >/dev/null 2>&1; then
                curl -sSfL "${CF_INSTALL_URL}" -o "${TMP_ARCHIVE}" || true
              elif command -v wget >/dev/null 2>&1; then
                wget -q -O "${TMP_ARCHIVE}" "${CF_INSTALL_URL}" || true
              fi
              if [ -f "${TMP_ARCHIVE}" ]; then
                tar -xzf "${TMP_ARCHIVE}" -C "${LOCAL_CF_DIR}" || true
                chmod +x "${LOCAL_CF_BIN}" || true
                echo "Local cf binary at ${LOCAL_CF_BIN}"
              else
                echo "Failed to download cf tarball to ${TMP_ARCHIVE} - continuing and will skip logout if missing"
              fi
            fi

            echo "=== INSTALL Python DEPENDENCIES (requests) IF pip3 PRESENT ==="
            if command -v pip3 >/dev/null 2>&1; then
              pip3 install --no-cache-dir requests || true
            elif command -v python3 >/dev/null 2>&1; then
              python3 -m pip install --user --no-cache-dir requests || true
            else
              echo "pip3/python3 unavailable - python script will fail unless python is present."
            fi

            echo "=== PREP DONE ==="
            command -v python3 || echo "python3 missing"
            command -v pip3 || echo "pip3 missing"
            command -v cf || echo "cf not in PATH (will use local cf if available at ${LOCAL_CF_BIN})"
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

    // Run the python script but ensure failures don't prevent the final cleanup stage from running.
    stage('Run Python Script') {
      steps {
        script {
          // This catchError ensures the pipeline continues to post/cleanup even if script fails.
          catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
            sh '''
              set -e
              # choose python binary
              if command -v python3 >/dev/null 2>&1; then
                PY=python3
              else
                echo "ERROR: python3 not available. Aborting script run."
                exit 2
              fi

              # build command
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
        // attempt to use system cf, else fall back to local CF binary in workspace
        sh '''
          set -e || true
          echo "POST: attempt cf logout (system cf or local cf)"
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
