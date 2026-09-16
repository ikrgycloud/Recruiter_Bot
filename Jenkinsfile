pipeline {

    agent any

    environment {

        // ==============================
        // AWS CONFIGURATION
        // ==============================
        AWS_REGION = "eu-north-1"
        AWS_ACCOUNT_ID = "032844082845"

        // ==============================
        // ECR REPOSITORIES
        // ==============================
        BACKEND_REPO = "recruiter-backend"
        FRONTEND_REPO = "recruiter-frontend"

        // Jenkins build number becomes Docker image tag
        IMAGE_TAG = "${BUILD_NUMBER}"

        // ECR registry
        ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

        // ==============================
        // APPLICATION EC2
        // ==============================
        APP_SERVER = "ubuntu@16.16.216.155"
        APP_DIR = "/opt/recruiter"

        // ==============================
        // APPLICATION URL
        // ==============================
        VITE_API_URL = "http://16.16.216.155:8011/api"
    }

    stages {

        // ============================================================
        // 1. CHECKOUT
        // ============================================================
        stage('Checkout') {

            steps {

                echo "======================================="
                echo "Checking out Recruiter Bot source code"
                echo "======================================="

                checkout scm

                echo "Checkout completed successfully"
            }
        }


        // ============================================================
        // 2. BUILD BACKEND
        // ============================================================
        stage('Build Backend') {

            steps {

                echo "======================================="
                echo "Building Backend Docker Image"
                echo "======================================="

                sh """
                    docker build \
                        -t ${BACKEND_REPO}:${IMAGE_TAG} \
                        ./backend
                """

                echo "Backend image built successfully"
            }
        }


        // ============================================================
        // 3. BUILD FRONTEND
        // ============================================================
        stage('Build Frontend') {

            steps {

                echo "======================================="
                echo "Building Frontend Docker Image"
                echo "======================================="

                sh """
                    docker build \
                        --build-arg VITE_API_URL="${VITE_API_URL}" \
                        -t ${FRONTEND_REPO}:${IMAGE_TAG} \
                        ./frontend
                """

                echo "Frontend image built successfully"
            }
        }


        // ============================================================
        // 4. LOGIN TO ECR
        // ============================================================
        stage('Login to ECR') {

            steps {

                echo "======================================="
                echo "Logging into Amazon ECR"
                echo "======================================="

                withCredentials([
                    [$class: 'AmazonWebServicesCredentialsBinding',
                     credentialsId: 'aws-ecr']
                ]) {

                    sh """
                        aws sts get-caller-identity

                        aws ecr get-login-password \
                            --region ${AWS_REGION} |
                        docker login \
                            --username AWS \
                            --password-stdin \
                            ${ECR_REGISTRY}
                    """
                }

                echo "ECR login successful"
            }
        }


        // ============================================================
        // 5. TAG IMAGES
        // ============================================================
        stage('Tag Images') {

            steps {

                echo "======================================="
                echo "Tagging Docker Images"
                echo "======================================="

                sh """
                    docker tag \
                        ${BACKEND_REPO}:${IMAGE_TAG} \
                        ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}

                    docker tag \
                        ${FRONTEND_REPO}:${IMAGE_TAG} \
                        ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}
                """

                echo "Docker images tagged successfully"
            }
        }


        // ============================================================
        // 6. PUSH BACKEND
        // ============================================================
        stage('Push Backend') {

            steps {

                echo "======================================="
                echo "Pushing Backend Image to ECR"
                echo "======================================="

                sh """
                    docker push \
                        ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}
                """

                echo "Backend image pushed successfully"
            }
        }


        // ============================================================
        // 7. PUSH FRONTEND
        // ============================================================
        stage('Push Frontend') {

            steps {

                echo "======================================="
                echo "Pushing Frontend Image to ECR"
                echo "======================================="

                sh """
                    docker push \
                        ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}
                """

                echo "Frontend image pushed successfully"
            }
        }


        // ============================================================
        // 8. DEPLOY TO APPLICATION EC2
        // ============================================================
        stage('Deploy to Application EC2') {

            steps {

                echo "======================================="
                echo "Deploying Recruiter Bot"
                echo "======================================="

                sshagent(credentials: ['app-server-ssh']) {

                    sh """

                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APP_SERVER} \
                        '
                            set -e

                            echo "======================================="
                            echo "Connected to Application EC2"
                            echo "======================================="

                            cd ${APP_DIR}

                            echo "======================================="
                            echo "Checking Docker"
                            echo "======================================="

                            docker --version

                            echo "======================================="
                            echo "Checking Docker Compose"
                            echo "======================================="

                            docker compose version

                            echo "======================================="
                            echo "Logging into Amazon ECR"
                            echo "======================================="

                            aws ecr get-login-password \
                                --region ${AWS_REGION} |
                            docker login \
                                --username AWS \
                                --password-stdin \
                                ${ECR_REGISTRY}

                            echo "======================================="
                            echo "Deployment Information"
                            echo "======================================="

                            echo "Image Tag: ${IMAGE_TAG}"

                            echo "Backend:"
                            echo "${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}"

                            echo "Frontend:"
                            echo "${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}"

                            echo "======================================="
                            echo "Setting Deployment Variables"
                            echo "======================================="

                            export IMAGE_TAG=${IMAGE_TAG}

                            export VITE_API_URL="${VITE_API_URL}"

                            echo "IMAGE_TAG=\${IMAGE_TAG}"
                            echo "VITE_API_URL=\${VITE_API_URL}"

                            echo "======================================="
                            echo "Pulling Backend Image"
                            echo "======================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                pull backend

                            echo "======================================="
                            echo "Pulling Frontend Image"
                            echo "======================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                pull frontend

                            echo "======================================="
                            echo "Starting Application"
                            echo "======================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                up -d

                            echo "======================================="
                            echo "Waiting for Services"
                            echo "======================================="

                            sleep 10

                            echo "======================================="
                            echo "Running Database Migration"
                            echo "======================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                exec -T backend \
                                alembic upgrade head

                            echo "======================================="
                            echo "Container Status"
                            echo "======================================="

                            docker compose \
                                -f docker-compose.prod.yml \
                                ps

                            echo "======================================="
                            echo "Deployment Completed"
                            echo "======================================="
                        '
                    """
                }
            }
        }


        // ============================================================
        // 9. VERIFY DEPLOYMENT
        // ============================================================
        stage('Verify Deployment') {

            steps {

                echo "======================================="
                echo "Verifying Recruiter Bot Deployment"
                echo "======================================="

                sshagent(credentials: ['app-server-ssh']) {

                    sh """

                        ssh \
                            -o StrictHostKeyChecking=no \
                            ${APP_SERVER} \
                        '
                            set -e

                            cd ${APP_DIR}

                            echo "======================================="
                            echo "Container Status"
                            echo "======================================="

                            export IMAGE_TAG=${IMAGE_TAG}

                            docker compose \
                                -f docker-compose.prod.yml \
                                ps

                            echo "======================================="
                            echo "Testing Backend"
                            echo "======================================="

                            curl \
                                --fail \
                                --silent \
                                --show-error \
                                http://localhost:8011/docs \
                                > /dev/null

                            echo "Backend is responding successfully"

                            echo "======================================="
                            echo "Testing Frontend"
                            echo "======================================="

                            curl \
                                --fail \
                                --silent \
                                --show-error \
                                http://localhost:86/ \
                                > /dev/null

                            echo "Frontend is responding successfully"

                            echo "======================================="
                            echo "Deployment Verification Successful"
                            echo "======================================="
                        '
                    """
                }
            }
        }
    }


    // ================================================================
    // POST ACTIONS
    // ================================================================
    post {

        // ============================================================
        // SUCCESS
        // ============================================================
        success {

            echo """
            =======================================
            RECRUITER BOT DEPLOYMENT SUCCESSFUL
            =======================================

            Build Number : ${BUILD_NUMBER}

            Backend Image:
            ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}

            Frontend Image:
            ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}

            Backend:
            http://16.16.216.155:8011/docs

            Frontend:
            http://16.16.216.155:86

            =======================================
            """
        }


        // ============================================================
        // FAILURE
        // ============================================================
        failure {

            echo """
            =======================================
            RECRUITER BOT DEPLOYMENT FAILED
            =======================================

            Build Number : ${BUILD_NUMBER}

            Please check the Jenkins console output
            for the failed stage and error.

            =======================================
            """
        }


        // ============================================================
        // ALWAYS
        // ============================================================
        always {

            echo "Cleaning Jenkins workspace..."

            cleanWs()
        }
    }
}
