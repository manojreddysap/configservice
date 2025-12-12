pipeline {
  agent {
    docker {
      image 'python:3.11-slim'    // official Python public image
      args  '-u root:root'        // run as root so we can apt-get install inside container
    }
  }

  parameters {
    choice(name: 'LANDSCAPE', choices: ['eu12','eu21','us31','eu12-fun','eu01-canary'], description: "Select landscape")
    choice(name: 'MODE', choices: ['set','read'], description: "set = Use this when you want to set the value at design service; read = Use this when you want to get token usage for a tenant")
    string(name: 'ENV_VARIABLE_VALUE', defaultValue: '', description: "Pass value here when you use mode as SET. Example: pass 19 if today's date is 20. Required when selected MODE is set")
    string(name: 'TENANT', defaultValue: '', description: "Provide tenant value here if you want to read the token usage for a specific tenant")
  }

  // 👇 INTERNAL values — NOT visible to users
  environment {
    APP_NAME = 'it-design-service'
    // JSON file will be selected dynamically below — no need for UI parameter
    CF_INSTALL_URL = 'https://packages.cloudfoundry.org/stable?release=linux64-binary&source=github'
  }

  stages {

    stage('Validate Tools & Params') {
      steps {
        script {
          // install runtime deps (cf, curl, requests) if missing
          sh '''
            set -e
            echo "Running inside: $(cat /etc/os-release 2>/dev/null || echo 'unknown')"
            # python3 is provided by the image
            command -v python3 >/dev/null 2>&1 || { echo "python3 missing — image seems wrong"; exit 1; }

            # Ensure apt-get is available (python:slim images have apt)
            if command -v apt-get >/dev/null 2>&1; then
              apt-get update -y
              # install tools needed to download cf and curl
              apt-get install -y --no-install-recommends wget curl ca-certificates unzip tar
            fi

            # Install cf CLI if not present
            if ! command -v cf >/dev/null 2>&1; then
              echo "cf not found — installing cf CLI..."
              TMPDIR=$(mktemp -d)
              cd "$TMPDIR"
              # download the official cloud foundry binary bundle (linux64)
              wget -q -O cf.tgz "${CF_INSTALL_URL}"
              tar -xzf cf.tgz -C /usr/local/bin || (echo "Extract to /usr/local/bin failed, trying /usr/bin"; tar -xzf cf.tgz -C /usr/bin)
              chmod +x /usr/local/bin/cf || true
              cd /
              rm -rf "$TMPDIR"
              command -v cf >/dev/null 2>&1 || { echo "cf installation failed"; exit 1; }
            else
              echo "cf already present: $(command -v cf)"
            fi

            # Install Python dependencies required by your script
            pip3 install --no-cache-dir requests || { echo "pip install requests failed"; exit 1; }

            # Verify required commands
            for cmd in python3 cf curl; do
              command -v $cmd >/dev/null 2>&1 || { echo "ERROR: required command '$cmd' missing"; exit 1; }
            done

            echo "Validation completed: python3 $(python3 --version), cf $(cf --version), curl $(curl --version | head -n1)"
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
          // 👇 internal JSON file selection based on MODE (hidden from UI)
          if (params.MODE == 'set') {
            env.CHOSEN_JSON = "set_env_parameter.json"
          } else {
            env.CHOSEN_JSON = "tenant_credentials.json"
          }

          echo "Using internal JSON file: ${env.CHOSEN_JSON}"

          sh """
            test -f "${env.CHOSEN_JSON}" || { 
              echo "ERROR: ${env.CHOSEN_JSON} does not exist"; 
              ls -la || true
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
      // cf should exist in the same container; logout safely
      sh "cf logout || true"
    }
  }
}
