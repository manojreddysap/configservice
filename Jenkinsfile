pipeline {
  agent {
    docker {
      image 'python:3.11-slim'        // Public Python image
      args  '-u root:root'            // Needed for apt-get installs
    }
  }

  parameters {
    choice(name: 'LANDSCAPE', choices: ['eu12','eu21','us31','eu12-fun','eu01-canary'], description: "Select landscape")
    choice(name: 'MODE', choices: ['set','read'], description: "set = update env parameter; read = get token usage")
    string(name: 'ENV_VARIABLE_VALUE', defaultValue: '', description: "Required when MODE=set. Example: pass 19 if today's date is 20.")
    string(name: 'TENANT', defaultValue: '', description: "Provide tenant value for read mode")
  }

  environment {
    APP_NAME = 'it-design-service'
    CF_INSTALL_URL = 'https://packages.cloudfoundry.org/stable?release=linux64-binary&source=github'
  }

  stages {

    stage('Validate Tools & Params') {
      steps {
        script {
          sh '''
            set -e
            echo "=== SYSTEM INFORMATION ==="
            cat /etc/os-release || true

            echo "=== INSTALLING REQUIRED TOOLS (curl, wget, unzip, tar) ==="
            if command -v apt-get >/dev/null 2>&1; then
              apt-get update -y
              apt-get install -y --no-install-recommends wget curl ca-certificates unzip tar
            fi

            echo "=== CHECK PYTHON3 ==="
            command -v python3 >/dev/null 2>&1 || { echo "python3 missing"; exit 1; }

            echo "=== INSTALL CF CLI IF MISSING ==="
            if ! command -v cf >/dev/null 2>&1; then
              echo "Installing Cloud Foundry CLI..."
              TMPDIR=$(mktemp -d)
              cd "$TMPDIR"
              wget -q -O cf.tgz "${CF_INSTALL_URL}"
              tar -xzf cf.tgz -C /usr/local/bin || tar -xzf cf.tgz -C /usr/bin
              chmod +x /usr/local/bin/cf || true
              cd /
              rm -rf "$TMPDIR"
            fi

            command -v cf >/dev/null 2>&1 || { echo "cf installation failed"; exit 1; }

            echo "=== INSTALL PYTHON DEPENDENCIES ==="
            pip3 install --no-cache-dir requests

            echo "=== FINAL VALIDATION ==="
            command -v python3
            command -v cf
            command -v curl
          '''

          if (params.MODE == 'set' && !params.ENV_VARIABLE_VALUE?.trim()) {
            error("MODE=set but ENV_VARIABLE_VALUE is empty.")
          }
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
            test -f "${env.CHOSEN_JSON}" || { 
              echo "ERROR: JSON file not found: ${env.CHOSEN_JSON}";
              ls -la;
              exit 1;
            }
          """
        }
      }
    }

    stage('Run Python Script') {
      steps {
        script {
          def cmd = [
            "python3",
            "set_env_parameter.py",
            "--mode", params.MODE,
            "--landscape", params.LANDSCAPE,
            "--json-file", env.CHOSEN_JSON
          ]

          if (params.MODE == "set") {
            cmd += ["--value", params.ENV_VARIABLE_VALUE, "--app-name", env.APP_NAME]
          }

          if (params.MODE == "read" && params.TENANT?.trim()) {
            cmd += ["--tenant", params.TENANT.trim()]
          }

          def fullCmd = cmd.collect { "'${it}'" }.join(" ")
          echo "Executing: ${fullCmd}"

          sh """
            set -e
            ${fullCmd}
          """
        }
      }
    }
  }

  post {
    always {
      script {
        sh '''
          echo "=== POST CLEANUP: CF LOGOUT ==="
          if command -v cf >/dev/null 2>&1; then
            cf logout || true
          else
            echo "cf not found — skipping logout"
          fi
        '''
      }
    }
  }
}
