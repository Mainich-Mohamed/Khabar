pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {
        stage('Python') {
            agent {
                docker {
                    image 'python:3.12-slim'
                    reuseNode true
                }
            }
            stages {
                stage('Install') {
                    steps {
                        sh 'python -m venv .ci-venv'
                        sh '.ci-venv/bin/pip install -q --disable-pip-version-check -r requirements-dev.txt'
                    }
                }
                stage('Unit tests') {
                    steps {
                        sh '.ci-venv/bin/pytest -p no:cacheprovider --junitxml=reports/junit.xml'
                    }
                }
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                }
            }
        }

        stage('Docker image') {
            steps {
                script {
                    env.CI_IMAGE = "khabar-ci:${env.BRANCH_NAME ?: 'local'}-${env.BUILD_NUMBER}"
                        .toLowerCase().replaceAll('[^a-z0-9_.:-]', '-')
                }
                sh 'docker build -f dockerfile -t "$CI_IMAGE" .'
                sh 'docker run --rm "$CI_IMAGE" --help'
            }
            post {  
                always {
                    sh 'docker image rm -f "$CI_IMAGE" || true'
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}