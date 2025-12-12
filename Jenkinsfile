pipeline {
  agent {
    docker {
      image 'python:3.11-slim'
      args  '-u root:root'
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
            echo "=== SYSTEM INFO ==="
            cat /etc/os-release || true

            if command -v apt-get >/dev/null 2>&1; then
              apt-get update -y
              apt-get install -y --no-install-recommends wget curl ca-certificates unzip tar
            fi

            command -v python3 >/dev/null 2>&1 || { echo "python3 missing"; exit 1; }

            if ! command -v cf >/dev/null 2>&1; then
              echo "Installing cf..."
              TMPDIR=$(mktemp -d)
              cd "$TMPDIR"
              wget -q -O cf.tgz "${CF_INSTALL_URL}"
              tar -xzf cf.tgz -C /usr/local/bin || tar -xzf cf.tgz -C /usr/bin
              chmod +x /usr/local/bin/cf || true
              cd /
              rm -rf "$TMPDIR"
            fi

            pip3 install --no-cache-dir requests

            for cmd in python3 cf curl; do
              command -v $cmd >/dev/null 2>&1 || { echo "ERROR: $cmd missing"; exit 1; }
            done

            echo "Validation OK: python3 $(python3 --version), cf $(cf --version)"
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
        echo "=== POST: ensuring cf logout inside a docker container (provides workspace) ==="
        // Use docker.image(...).inside to ensure a workspace/FilePath is available for sh.
        docker.image('python:3.11-slim').inside('-u root:root') {
          sh '''
            if command -v cf >/dev/null 2>&1; then
               echo "Running cf logout..."
               cf logout || true
            else
               echo "cf not available in container; skipping logout"
            fi
          '''
        }
      }
    }
  }
}
