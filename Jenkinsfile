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

        stage('DB integration tests') {
            steps {
                script {
                    docker.image('pgvector/pgvector:pg16')
                            .withRun('-e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test') { pg ->
                        // -h 127.0.0.1 on purpose: during first-time init Postgres runs a temporary
                        // server on the unix socket only, so a socket check can say "ready" too early
                        timeout(time: 1, unit: 'MINUTES') {
                            sh "until docker exec ${pg.id} pg_isready -h 127.0.0.1 -U test -d test; do sleep 1; done"
                        }
                        docker.image('python:3.12-slim').inside("--link ${pg.id}:testdb") {
                            sh '''
                                TEST_DATABASE_URL=postgresql://test:test@testdb:5432/test \
                                    .ci-venv/bin/pytest -p no:cacheprovider -rs tests/integration \
                                    --junitxml=reports/junit-db.xml
                            '''
                        }
                    }
                }
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/junit-db.xml'
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