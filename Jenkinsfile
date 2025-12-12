pipeline {
  agent any

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
  }

  stages {

    stage('Validate Tools & Params') {
      steps {
        script {
          sh '''
            set -e
            command -v python3 >/dev/null 2>&1 || { echo "python3 missing"; exit 1; }
            command -v cf >/dev/null 2>&1 || { echo "cf missing"; exit 1; }
            command -v curl >/dev/null 2>&1 || { echo "curl missing"; exit 1; }
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
      sh "cf logout || true"
    }
  }
}
